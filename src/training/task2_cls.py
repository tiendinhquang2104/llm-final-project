"""F-cls training and inference: Qwen + LoRA + a 10-way sigmoid head (multi-label BCE), docs/task2_finetune_plan.md.

Kaggle-safe by design (sessions die at 12h, interactive ones earlier):
- checkpoints (adapter + optimizer + scheduler + RNG) every `train.save_steps` into <run>/checkpoints/;
- a deadline: before it is reached the trainer saves and stops cleanly (status "paused"), so the notebook ends
  normally and /kaggle/working is kept with the version; the next session resumes from that checkpoint, found in
  <run>/checkpoints or in any --resume-dir (e.g. the previous version mounted under /kaggle/input);
- optional Hugging Face Hub mirror of the last checkpoint (HF_TOKEN + --hub-repo) for hard crashes;
- status.json "done" + adapter/ make a finished run a no-op when the notebook is run again.
"""
from __future__ import annotations

import json
import math
import os
import platform
import shutil
import time
from pathlib import Path

from src.task2.labels import LABELS

CKPT_PREFIX = "checkpoint-"


# ---------------------------------------------------------------------------------------------- checkpoints


def _step(path: Path) -> int:
    try:
        return int(path.name[len(CKPT_PREFIX):])
    except ValueError:
        return -1


def _complete(path: Path) -> bool:
    """A checkpoint is usable when the trainer state and the adapter weights were fully written."""
    return (path / "trainer_state.json").exists() and any(path.glob("adapter_model.*"))


def find_checkpoint(run_dir, run_name: str, resume_dirs=()) -> Path | None:
    """Latest complete checkpoint of this run: <run_dir>/checkpoints/checkpoint-N first, else the highest one found
    under any resume dir (a previous Kaggle version mounted read-only), copied into <run_dir>/checkpoints/."""
    run_dir = Path(run_dir)
    own = [p for p in (run_dir / "checkpoints").glob(f"{CKPT_PREFIX}*") if _complete(p)]
    found = []
    for d in resume_dirs or ():
        d = Path(d)
        if d.exists():
            found += [p for p in d.rglob(f"{CKPT_PREFIX}*")
                      if p.is_dir() and p.parent.name == "checkpoints" and p.parent.parent.name == run_name
                      and _complete(p)]
    best_own = max(own, key=_step, default=None)
    best_ext = max(found, key=_step, default=None)
    if best_ext is not None and (best_own is None or _step(best_ext) > _step(best_own)):
        dst = run_dir / "checkpoints" / best_ext.name
        if not dst.exists():
            shutil.copytree(best_ext, dst)
        return dst
    return best_own


def read_status(run_dir) -> dict:
    p = Path(run_dir) / "status.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_status(run_dir, **kw) -> None:
    p = Path(run_dir) / "status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({**kw, "time": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(p)


# ---------------------------------------------------------------------------------------------- callbacks


def make_callbacks(run_dir, deadline: float | None, hub=None):
    from transformers import TrainerCallback

    class Deadline(TrainerCallback):
        """Save + stop when the next step would cross the deadline (margin = 2 steps + 3 min for the save)."""

        def __init__(self):
            self.paused = False
            self.t_last = None
            self.step_s = 0.0

        def on_step_end(self, args, state, control, **kw):
            now = time.time()
            if self.t_last is not None:
                dt = now - self.t_last
                self.step_s = dt if not self.step_s else 0.8 * self.step_s + 0.2 * dt
            self.t_last = now
            if deadline is not None and now + 2 * self.step_s + 180 >= deadline and state.global_step < state.max_steps:
                self.paused = True
                control.should_save = True
                control.should_training_stop = True
            return control

    class Log(TrainerCallback):
        def __init__(self):
            self.path = Path(run_dir) / "train_log.jsonl"
            self.t0 = time.time()

        def on_log(self, args, state, control, logs=None, **kw):
            row = {"step": state.global_step, "epoch": state.epoch, "elapsed_s": round(time.time() - self.t0, 1),
                   **(logs or {})}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    class HubMirror(TrainerCallback):
        def on_save(self, args, state, control, **kw):
            ckpt = Path(args.output_dir) / f"{CKPT_PREFIX}{state.global_step}"
            if ckpt.exists():
                hub.push(ckpt)

    cbs = [Deadline(), Log()]
    if hub is not None:
        cbs.append(HubMirror())
    return cbs


class HubSync:
    """Mirror of the last checkpoint of one run on a private HF Hub repo (path <run_name>/last)."""

    def __init__(self, repo_id: str, run_name: str, token: str | None = None):
        from huggingface_hub import HfApi
        self.api, self.repo, self.run, self.token = HfApi(token=token), repo_id, run_name, token
        self.api.create_repo(repo_id, private=True, exist_ok=True)

    def push(self, ckpt: Path) -> None:
        try:
            self.api.upload_folder(folder_path=str(ckpt), repo_id=self.repo, path_in_repo=f"{self.run}/last",
                                   delete_patterns="*", commit_message=f"{self.run} {ckpt.name}")
        except Exception as exc:  # never kill training because the mirror failed
            print(f"[hub] upload failed: {exc!r}", flush=True)

    def pull(self, run_dir) -> Path | None:
        from huggingface_hub import snapshot_download
        try:
            local = snapshot_download(self.repo, allow_patterns=[f"{self.run}/last/*"], token=self.token)
        except Exception as exc:
            print(f"[hub] nothing to resume from: {exc!r}", flush=True)
            return None
        src = Path(local) / self.run / "last"
        if not (src / "trainer_state.json").exists():
            return None
        step = json.loads((src / "trainer_state.json").read_text())["global_step"]
        dst = Path(run_dir) / "checkpoints" / f"{CKPT_PREFIX}{step}"
        if not dst.exists():
            shutil.copytree(src, dst)
        return dst


# ---------------------------------------------------------------------------------------------- model / data


def load_tokenizer(name: str, revision: str | None = None):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name, revision=revision)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"
    tok.truncation_side = "left"  # keep the code and the compile/run signals at the end
    return tok


def encode(tok, rows: list[dict], max_length: int) -> list[dict]:
    out = []
    for r in rows:
        text = tok.apply_chat_template(r["messages"], tokenize=False)
        enc = tok(text, truncation=True, max_length=max_length)
        out.append({"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]})
    return out


def _dtype_kwarg() -> str:
    """`dtype` from transformers 4.56 on (`torch_dtype` is deprecated there), `torch_dtype` before."""
    import transformers
    major, minor = (int(x) for x in transformers.__version__.split(".")[:2])
    return "dtype" if (major, minor) >= (4, 56) else "torch_dtype"


def load_model(mcfg: dict, lcfg: dict | None, train: bool, adapter=None, device_map=None):
    """4-bit (nf4, fp16 compute, head kept unquantized) on CUDA when model.load_in_4bit; plain fp32 otherwise (CPU
    smoke tests). train=True wraps a new LoRA (task SEQ_CLS, head trained in full); adapter=<dir> loads one."""
    import torch
    from transformers import AutoModelForSequenceClassification, BitsAndBytesConfig

    cuda = torch.cuda.is_available()
    kw = dict(num_labels=len(LABELS), problem_type="multi_label_classification", revision=mcfg.get("revision"),
              # SDPA (memory-efficient kernel on T4) instead of eager attention: eager materialises the full
              # heads x seq x seq score matrix in fp32 (28 x 3.5k^2 x 4 B = 1.3 GiB per layer) and OOMs on long gold
              attn_implementation=mcfg.get("attn_implementation", "sdpa"))
    dtype_kw = _dtype_kwarg()
    q4 = bool(mcfg.get("load_in_4bit")) and cuda
    if q4:
        kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16, llm_int8_skip_modules=["score"])
        kw[dtype_kw] = torch.float16
        kw["device_map"] = device_map or {"": 0}
    elif cuda:
        kw[dtype_kw] = torch.float16
        kw["device_map"] = device_map or {"": 0}
    model = AutoModelForSequenceClassification.from_pretrained(mcfg["name"], **kw)
    tok_pad = mcfg.get("pad_token_id")
    if tok_pad is not None:
        model.config.pad_token_id = tok_pad
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
    if adapter is not None:
        model = PeftModel.from_pretrained(model, str(adapter), is_trainable=train)
    elif train:
        if q4:
            model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                                    gradient_checkpointing_kwargs={"use_reentrant": False})
        model = get_peft_model(model, LoraConfig(
            task_type=TaskType.SEQ_CLS, r=int(lcfg["r"]), lora_alpha=int(lcfg["alpha"]),
            lora_dropout=float(lcfg["dropout"]), target_modules=list(lcfg["target_modules"]),
            modules_to_save=["score"]))
    if q4 or train:  # the head (and LoRA) train / run in fp32 for stable BCE logits
        for n, p in model.named_parameters():
            if "score" in n and p.dtype != torch.float32:
                p.data = p.data.float()
    cast_head_inputs(model)
    return model


def is_head(name: str) -> bool:
    return "score" in name.split(".")


def zero_head(model) -> int:
    """Start the trainable classification head at 0 (every logit 0, p = 0.5). The default random head times the
    large last hidden state of Qwen gives saturated logits at step 0: BCE of 4-15 and grad norms of 50-500 on
    Kaggle, so the clipped updates were mostly noise. Returns the number of zeroed tensors."""
    import torch
    n = 0
    with torch.no_grad():
        for name, p in model.named_parameters():
            if p.requires_grad and is_head(name):
                p.zero_()
                n += 1
    return n


def cast_head_inputs(model) -> int:
    """Feed the classification head in its own dtype. The head is kept in fp32, but at prediction time there is no
    autocast and the backbone returns fp16 hidden states ("expected mat1 and mat2 to have the same dtype: Half !=
    float"). Returns the number of hooked layers."""
    import torch

    def _cast(module, args):
        x = args[0]
        return (x.to(module.weight.dtype), *args[1:]) if x.dtype != module.weight.dtype else None

    n = 0
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.Linear) and "score" in name.split(".") \
                and not getattr(mod, "_head_cast_hooked", False):
            mod.register_forward_pre_hook(_cast)
            mod._head_cast_hooked = True
            n += 1
    return n


class _Rows:
    def __init__(self, enc, ys=None, ws=None):
        self.enc, self.ys, self.ws = enc, ys, ws

    def __len__(self):
        return len(self.enc)

    def __getitem__(self, i):
        item = dict(self.enc[i])
        if self.ys is not None:
            item["labels"] = [float(v) for v in self.ys[i]]
            item["weight"] = float(self.ws[i])
        return item


def drop_full_mask(batch: dict) -> dict:
    """Remove an all-ones attention_mask (no padding in the batch). With an explicit mask, SDPA on T4 falls back
    to the "math" kernel, which builds the full heads x seq x seq matrix (28 x 4096^2 x 4 B = 1.75 GiB); without
    it the causal memory-efficient kernel is used. Qwen2 sequence classification pools the last token from
    input_ids, so the mask is not needed for pooling."""
    m = batch.get("attention_mask")
    if m is not None and bool(m.all()):
        batch.pop("attention_mask")
    return batch


def make_trainer_cls():
    import torch
    from transformers import Trainer

    class WeightedBCETrainer(Trainer):
        """BCE with per-label pos_weight and per-sample weight (source weight)."""

        pos_weight = None
        head_lr = None  # own learning rate for the (zero-initialised) head; None = args.learning_rate

        def create_optimizer(self, *a, **kw):
            if self.optimizer is None and self.head_lr:
                params = [(n, p) for n, p in self.model.named_parameters() if p.requires_grad]
                head = [p for n, p in params if is_head(n)]
                rest = [p for n, p in params if not is_head(n)]
                cls, okw = Trainer.get_optimizer_cls_and_kwargs(self.args, self.model)
                self.optimizer = cls(
                    [{"params": rest, "lr": self.args.learning_rate, "weight_decay": self.args.weight_decay},
                     {"params": head, "lr": float(self.head_lr), "weight_decay": 0.0}], **okw)
            return super().create_optimizer(*a, **kw)

        def compute_loss(self, model, inputs, return_outputs=False, **kw):
            labels = inputs.pop("labels").float()
            weight = inputs.pop("weight").float()
            out = model(**drop_full_mask(inputs))
            logits = out.logits.float()
            pw = torch.tensor(self.pos_weight, device=logits.device, dtype=torch.float32)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=pw,
                                                                        reduction="none").mean(dim=1)
            loss = (loss * weight).sum() / weight.sum()
            return (loss, out) if return_outputs else loss

    return WeightedBCETrainer


# ---------------------------------------------------------------------------------------------- train / predict


def env_info() -> dict:
    import torch
    info = {"python": platform.python_version(), "torch": torch.__version__, "platform": platform.platform()}
    for mod in ("transformers", "peft", "bitsandbytes", "accelerate"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:
            info[mod] = None
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_mem_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 1)
    return info


def resolved_revision(name: str, revision: str | None) -> str | None:
    """Commit hash of the model on the Hub (reproducibility); None offline / for a local path."""
    if Path(name).exists():
        return None
    try:
        from huggingface_hub import HfApi
        return HfApi().model_info(name, revision=revision).sha
    except Exception:
        return None


def train_run(cfg: dict, train_rows: list[dict], weights: list[float], pos_weight: list[float], run_dir,
              deadline: float | None = None, resume_dirs=(), hub: HubSync | None = None) -> dict:
    """Train (or resume) one run. Returns the status dict ("done" with adapter/ or "paused")."""
    import torch
    from transformers import DataCollatorWithPadding, TrainingArguments, set_seed

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    st = read_status(run_dir)
    if st.get("state") == "done" and (run_dir / "adapter").exists():
        print(f"[train] {run_dir.name}: already done", flush=True)
        return st
    mcfg, tcfg, seed = dict(cfg["model"]), cfg["train"], int(cfg.get("seed", 42))
    set_seed(seed)
    tok = load_tokenizer(mcfg["name"], mcfg.get("revision"))
    mcfg["pad_token_id"] = tok.pad_token_id
    # training may use a shorter context than prediction: activation memory grows with the longest record
    # (gold / gold-mutant reach ~3.5k tokens), the left side (prompt start) is what gets cut
    max_len = int(tcfg.get("max_length") or mcfg.get("max_length", 4096))
    enc = encode(tok, train_rows, max_len)
    n_cut = sum(len(e["input_ids"]) >= max_len for e in enc)
    print(f"[train] {run_dir.name}: max_length={max_len}, {n_cut}/{len(enc)} rows truncated", flush=True)
    ds = _Rows(enc, [r["y"] for r in train_rows], weights)
    ckpt = find_checkpoint(run_dir, run_dir.name, resume_dirs)
    if ckpt is None and hub is not None:
        ckpt = hub.pull(run_dir)
    print(f"[train] {run_dir.name}: {len(ds)} rows, resume={ckpt}", flush=True)
    model = load_model(mcfg, cfg["lora"], train=True)
    if tcfg.get("head_init") == "zero":  # a resumed run then loads its trained head from the checkpoint
        zero_head(model)
    if hasattr(model, "print_trainable_parameters"):
        model.print_trainable_parameters()
    attn = getattr(getattr(model, "config", None), "_attn_implementation", None)
    print(f"[train] {run_dir.name}: attention={attn}", flush=True)
    cuda = torch.cuda.is_available()
    bs, accum = int(tcfg.get("batch_size", 1)), int(tcfg.get("grad_accum", 16))
    total = math.ceil(len(ds) / (bs * accum)) * float(tcfg["epochs"])
    warmup = int(round(float(tcfg.get("warmup_ratio", 0.03)) * total))  # warmup_ratio is gone in transformers 5
    args = TrainingArguments(
        output_dir=str(run_dir / "checkpoints"), num_train_epochs=float(tcfg["epochs"]),
        learning_rate=float(tcfg["lr"]), warmup_steps=warmup,
        lr_scheduler_type=tcfg.get("scheduler", "cosine"), weight_decay=float(tcfg.get("weight_decay", 0.0)),
        max_grad_norm=float(tcfg.get("max_grad_norm", 1.0)),
        per_device_train_batch_size=bs, gradient_accumulation_steps=accum,
        gradient_checkpointing=cuda, gradient_checkpointing_kwargs={"use_reentrant": False} if cuda else None,
        fp16=cuda, optim="paged_adamw_8bit" if cuda and mcfg.get("load_in_4bit") else "adamw_torch",
        logging_steps=int(tcfg.get("logging_steps", 5)), save_strategy="steps",
        save_steps=int(tcfg.get("save_steps", 25)), save_total_limit=int(tcfg.get("save_total_limit", 2)),
        save_only_model=False, report_to="none", seed=seed, data_seed=seed, remove_unused_columns=False,
        dataloader_num_workers=0, disable_tqdm=not os.environ.get("TQDM", ""),
    )
    trainer_cls = make_trainer_cls()
    trainer_cls.pos_weight = list(pos_weight)
    trainer_cls.head_lr = tcfg.get("head_lr")
    print(f"[train] {run_dir.name}: lr={tcfg['lr']} head_lr={tcfg.get('head_lr')} head_init={tcfg.get('head_init')} "
          f"warmup_steps={warmup}/{int(total)}", flush=True)
    cbs = make_callbacks(run_dir, deadline, hub)
    trainer = trainer_cls(model=model, args=args, train_dataset=ds, data_collator=DataCollatorWithPadding(tok),
                          callbacks=cbs)
    t0 = time.time()
    if cuda:
        torch.cuda.reset_peak_memory_stats()
    trainer.train(resume_from_checkpoint=str(ckpt) if ckpt else None)
    took = time.time() - t0
    peak = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2) if cuda else None
    info = {"global_step": trainer.state.global_step, "max_steps": trainer.state.max_steps,
            "session_train_s": round(took, 1), "peak_gpu_gb": peak}
    paused = cbs[0].paused
    if not paused:
        trainer.save_model(str(run_dir / "adapter"))
    del trainer, model  # free the training model/optimizer before prediction loads a fresh one
    empty_cuda()
    if paused:
        write_status(run_dir, state="paused", **info)
        print(f"[train] {run_dir.name}: paused at step {info['global_step']}/{info['max_steps']} (deadline)", flush=True)
        return read_status(run_dir)
    write_status(run_dir, state="done", **info)
    print(f"[train] {run_dir.name}: done ({info['global_step']} steps, {took / 60:.1f} min)", flush=True)
    return read_status(run_dir)


def empty_cuda() -> None:
    import gc
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def token_batches(lengths: list[int], max_batch: int, token_budget: int) -> list[list[int]]:
    """Indices grouped longest first so that each padded batch (n x longest) stays within `token_budget` tokens
    (a 4k-token record runs alone; short ones share a batch, up to `max_batch`)."""
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    out, cur = [], []
    for i in order:
        longest = lengths[cur[0]] if cur else lengths[i]
        if cur and (len(cur) + 1 > max_batch or (len(cur) + 1) * longest > token_budget):
            out.append(cur)
            cur = []
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def predict(cfg: dict, rows: list[dict], adapter, batch_size: int = 4, token_budget: int | None = None) -> list[dict]:
    """[{"id", "probs": {label: p}}] for `rows` with the trained adapter (fp16 on GPU).

    Batches are capped by padded tokens (`token_budget`, default model.max_length) and a batch that still runs
    out of memory is split in halves and retried, so prediction never dies on the longest public records
    (OOM seen with 4 x 4096 tokens through the fp32 LoRA path of down_proj)."""
    import torch
    from transformers import DataCollatorWithPadding

    mcfg = dict(cfg["model"])
    tok = load_tokenizer(mcfg["name"], mcfg.get("revision"))
    mcfg["pad_token_id"] = tok.pad_token_id
    model = load_model(mcfg, None, train=False, adapter=adapter)
    model.eval()
    max_len = int(mcfg.get("max_length", 4096))
    enc = encode(tok, rows, max_len)
    budget = int(token_budget or max_len)
    coll = DataCollatorWithPadding(tok)
    dev = next(model.parameters()).device
    probs = [None] * len(rows)

    oom = getattr(torch, "OutOfMemoryError", None) or torch.cuda.OutOfMemoryError

    def run(idx: list[int]) -> None:
        try:
            batch = drop_full_mask({k: v.to(dev) for k, v in coll([enc[i] for i in idx]).items()})
            with torch.no_grad():
                p = torch.sigmoid(model(**batch).logits.float()).cpu().tolist()
        except oom:
            if len(idx) == 1:
                raise
            batch = None
            empty_cuda()
            half = len(idx) // 2
            run(idx[:half])
            run(idx[half:])
            return
        for i, pi in zip(idx, p):
            probs[i] = pi

    for idx in token_batches([len(e["input_ids"]) for e in enc], batch_size, budget):
        run(idx)
    return [{"id": r["id"], "probs": {lab: round(float(v), 6) for lab, v in zip(LABELS, p)}}
            for r, p in zip(rows, probs)]
