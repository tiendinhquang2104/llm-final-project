"""Opt-in bounded R15 experiment; importing this module never loads a model."""
from __future__ import annotations

import hashlib
import json
import ast
import importlib
import importlib.metadata
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def execution_identity(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require_identity(expected, value):
    if expected != execution_identity(value):
        raise ValueError("experiment identity mismatch")


def adapter_identity(path):
    if path is None:
        return None
    path = Path(path).resolve()
    tensors = sorted(path.glob("*.safetensors")) + sorted(path.glob("adapter_model*.bin"))
    if not tensors or not (path / "adapter_config.json").is_file():
        raise ValueError("adapter requires config and tensor bytes")
    files = [path / "adapter_config.json", *tensors]
    return {"files": {p.name: sha_file(p) for p in files}}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text())


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def require_branch(repo):
    branch = git(repo, "branch", "--show-current")
    if branch != "fix/task3-strict-feedback":
        raise ValueError("branch mismatch: " + branch)


def snapshot_runtime(repo, run, out):
    """Read git blobs only. Isolate absolute imports; retain original bytes too."""
    commit = run["git_head"]
    package = "r15abc_historical"
    pending = list(run["implementation_sha256"])
    original, graph = {}, {}
    while pending:
        rel = pending.pop()
        if rel in original:
            continue
        raw = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + rel])
        expected = run["implementation_sha256"].get(rel)
        if expected and hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("historical blob mismatch: " + rel)
        original[rel] = raw
        imports = []
        for node in ast.walk(ast.parse(raw)):
            names = ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                     else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                if name.startswith("src."):
                    dep = name.replace(".", "/") + ".py"
                    if dep not in imports:
                        imports.append(dep)
                        pending.append(dep)
        graph[rel] = sorted(imports)
    manifest = {"commit": commit, "namespace": package, "import_graph": graph, "files": {}}
    for rel, raw in original.items():
        p = Path(out) / "vendor/original" / rel
        if p.exists() and p.read_bytes() != raw:
            raise ValueError("historical snapshot drift")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        if rel.startswith("src/"):
            active = Path(out) / "vendor/active" / package / rel[4:]
            active.parent.mkdir(parents=True, exist_ok=True)
            for parent in [active.parent, *active.parents]:
                if parent == Path(out) / "vendor/active":
                    break
                (parent / "__init__.py").touch(exist_ok=True)
            transformed = re.sub(r"\b(from|import) src\.", r"\1 " + package + ".", raw.decode()).encode()
            if active.exists() and active.read_bytes() != transformed:
                raise ValueError("active historical snapshot drift")
            active.write_bytes(transformed)
            active_sha = hashlib.sha256(transformed).hexdigest()
        else:
            active_sha = None
        current = Path(repo) / rel
        manifest["files"][rel] = {"original_sha256": hashlib.sha256(raw).hexdigest(),
                                   "active_sha256": active_sha,
                                   "current_sha256": sha_file(current) if current.is_file() else None}
    return manifest


def historical_module(out, name):
    vendor = str(Path(out).resolve() / "vendor/active")
    if vendor not in sys.path:
        sys.path.insert(0, vendor)
    module = importlib.import_module("r15abc_historical." + name)
    if not Path(module.__file__).resolve().is_relative_to(Path(vendor)):
        raise ValueError("historical import escaped private snapshot")
    return module


def inventory_inputs(repo: Path, config: dict) -> dict:
    repo = Path(repo).resolve()
    require_branch(repo)
    historical = Path(config["historical_root"])
    out = repo / config["out"]
    run_path = historical / "round15/public-candidate-zero/run.json"
    run = read_json(run_path)
    runtime = snapshot_runtime(repo, run, out)
    write_json(out / "history-comparison.json", runtime)
    import torch
    inventory = {"repo": str(repo), "branch": git(repo, "branch", "--show-current"),
                 "head": git(repo, "rev-parse", "HEAD"),
                 "status": git(repo, "status", "--porcelain=v1"),
                 "python": sys.executable, "cuda": torch.version.cuda,
                 "cuda_available": torch.cuda.is_available(), "gpu_count": torch.cuda.device_count(),
                 "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                 "packages": {p: importlib.metadata.version(p) for p in
                              ("torch", "transformers", "peft", "bitsandbytes", "tokenizers", "accelerate")},
                 "historical_run": {"path": str(run_path), "sha256": sha_file(run_path)},
                 "runtime": runtime, "artifacts": {},
                 "score_claims": [{"value": "~0.34", "source": "user claim recorded in attached plan", "verified": False},
                                  {"value": 0.3834, "source": "historical report claim", "verified": False}],
                 "leaderboard_receipt": None, "model_loaded": False}
    for name in ("round15", "direct-sft-v1-20261021", "direct-sft-v2-20261021"):
        root = historical / name
        inventory["artifacts"][name] = {"path": str(root), "exists": root.is_dir(),
                                       "adapters": {str(p.relative_to(root)): sha_file(p)
                                                    for p in root.rglob("adapter_model.safetensors")}}
    write_json(out / "inventory.json", inventory)
    return inventory


def arm_messages(record, arm, examples, *, runtime=None):
    if arm not in "ABC" or len(arm) != 1:
        raise ValueError("arm must be A, B or C")
    if runtime is None:
        from src.task3 import round15 as runtime
    shots = [e for e in examples if e["level"] == int(record.target_feedback_level[6])][:2] if arm == "B" else []
    return runtime.build_messages(record, shots)


def validate_export(predictions: list[dict], requested_levels: dict) -> dict:
    from src.task3.round15 import parse_response
    errors, seen = [], set()
    for p in predictions:
        try:
            if not isinstance(p, dict) or set(p) != {"sample_id", "output"}:
                raise ValueError("record schema")
            sid = p["sample_id"]
            if sid in seen:
                raise ValueError("duplicate ID")
            seen.add(sid)
            if sid not in requested_levels:
                raise ValueError("extra ID")
            parse_response(json.dumps(p["output"], ensure_ascii=False))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(str(exc))
    missing = sorted(set(requested_levels) - seen)
    if missing:
        errors.append("missing IDs")
    if [p.get("sample_id") for p in predictions if isinstance(p, dict)] != list(requested_levels):
        errors.append("ID order mismatch")
    return {"valid": not errors and len(predictions) == len(requested_levels), "count": len(predictions),
            "expected": len(requested_levels), "missing": missing, "errors": errors}


def stable_json(path, value):
    if Path(path).exists():
        if read_json(path) != value:
            raise ValueError("frozen artifact identity drift: " + str(path))
    else:
        write_json(path, value)


def verify_file_hashes(files):
    for name, digest in files.items():
        if not Path(name).is_file() or sha_file(name) != digest:
            raise ValueError("artifact identity drift: " + name)


def append_event(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line] if Path(path).exists() else []


class ReservedBackend:
    """Durably charge a call before entering the unchanged R15 backend."""
    def __init__(self, backend, path, identity, sample_id):
        self.backend, self.path, self.identity, self.sample_id = backend, Path(path), identity, sample_id
        self.tokenizer = backend.tokenizer

    def generate(self, messages, config):
        reservations = jsonl(self.path)
        if len(reservations) >= 3:
            raise ValueError("reserved attempt budget exhausted")
        append_event(self.path, {"identity": self.identity, "sample_id": self.sample_id,
                                 "attempt": len(reservations) + 1, "prompt_sha256": execution_identity(messages),
                                 "input_tokens": len(self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)),
                                 "reserved_unix": time.time()})
        return self.backend.generate(messages, config)


def preflight_records(records, arm, examples, tokenizer, config, *, runtime=None):
    if runtime is None:
        from src.task3 import round15 as runtime
    budgets = []
    for r in records:
        level = int(r.target_feedback_level[6])
        shots = [e for e in examples if e["level"] == level] if arm == "B" else []
        cap = config.get("level4_max_tokens", 1536) if level == 4 else config.get("max_new_tokens", 1024)
        try:
            messages, info = runtime.fitted_messages(r, shots, tokenizer,
                {**config, "max_new_tokens": cap, "few_shot_k": 2 if arm == "B" else 0})
            budgets.append({"sample_id": r.sample_id, "status": "ready", "prompt_sha256": execution_identity(messages), **info})
        except ValueError as exc:
            budgets.append({"sample_id": r.sample_id, "status": "query_over_context", "reason": str(exc)})
    return budgets


def require_public_sources(records, fingerprints):
    from src.task3.r15_abc_data import signature
    expected = {r["sample_id"]: r for r in fingerprints}
    if {r.sample_id for r in records} != set(expected) or len(records) != len(expected):
        raise ValueError("public source population mismatch")
    for record in records:
        actual = signature(dict(sample_id=record.sample_id, family=record.exam_id, code=record.code,
                                source_sha256=sha_file(record.code_path)))
        old = expected[record.sample_id]
        if any(actual.get(k) != old.get(k) for k in ("source_sha256", "code_identity", "structural_shingles")):
            # The opaque direct-SFT fingerprint uses code_identity; the ABC
            # signature exposes the same token digest under its explicit name.
            if (actual["source_sha256"] != old.get("source_sha256")
                    or actual["normalized_token_sha256"] != old.get("code_identity")
                    or actual["structural_shingles"] != old.get("structural_shingles")):
                raise ValueError("public source fingerprint identity mismatch")


def require_selected_checkpoint(split, requested, selected):
    if split != "checkpoint-dev" and requested not in ("selected", selected):
        raise ValueError("downstream C must use the semantically selected checkpoint")


def verify_selected_adapter(out):
    out = Path(out)
    trained = read_json(out / "C/training/training-result.json")
    selected = read_json(out / "checkpoint-selection.json")
    if trained["status"] != "complete":
        raise ValueError("selected adapter training is incomplete")
    choice = next(c for c in trained["checkpoints"] if c["name"] == selected["selected"])
    sealed = next(c for c in selected["candidates"] if c["name"] == selected["selected"])
    if (choice["step"] != selected["step"] or sealed["adapter_identity"] != choice["adapter_identity"]
            or adapter_identity(choice["adapter_path"]) != choice["adapter_identity"]):
        raise ValueError("selected adapter dependency identity mismatch")
    return choice


def run_arm(records: list, arm: str, config: dict, out: Path, *, examples: list[dict],
            adapter: Path | None, backend=None) -> dict:
    """Unmodified R15 controller per request, with durable terminal-error semantics."""
    if arm not in ("A", "B", "C") or (arm != "C" and adapter is not None) or (arm == "C" and adapter is None):
        raise ValueError("arm/adapter contract mismatch")
    if config.get("max_attempts", 3) != 3:
        raise ValueError("ABC requires a total budget of three attempts")
    if config.get("runtime_out"):
        runtime = historical_module(config["runtime_out"], "task3.round15")
        runner = historical_module(config["runtime_out"], "task3.round15_runner")
        inference = historical_module(config["runtime_out"], "task3.inference")
    else:
        from src.task3 import round15 as runtime, round15_runner as runner, inference
    active = {**config, "prompt_variant": "few_shot" if arm == "B" else "zero_shot", "few_shot_k": 2 if arm == "B" else 0}
    if config.get("adapter"):
        raise ValueError("adapter must be explicit, not inherited from common configuration")
    chosen_bank = list(examples) if arm == "B" else []
    tensor_identity = adapter_identity(adapter)
    if backend is None:
        backend = inference.HFBackend({**active, **({"adapter": str(adapter)} if adapter else {})})
    if hasattr(backend, "model"):
        model = backend.model
        lora_names = [n for n, _ in model.named_parameters() if "lora_" in n]
        if bool(lora_names) != (arm == "C"):
            raise ValueError("active adapter does not match arm")
        if arm == "C" and not getattr(model, "peft_config", None):
            raise ValueError("C requires an active PEFT adapter")
        model.generation_config.max_time = float(config.get("generation_max_time_s", 45))
    binding = {"arm": arm, "config": active, "adapter": tensor_identity, "bank": chosen_bank,
               "tokenizer": inference.tokenizer_metadata(backend.tokenizer),
               "inputs": [{"sample_id": r.sample_id, "payload": runtime.query_payload(r)} for r in records]}
    out = Path(out)
    stable_json(out / "execution-binding.json", {"identity": execution_identity(binding), "binding": binding})
    identity = execution_identity(binding)
    active["abc_execution_identity"] = identity
    predictions, traces, errors = [], [], {}
    fresh_calls = 0
    for index, record in enumerate(records):
        request_out = out / "requests" / execution_identity(record.sample_id)[:24]
        terminal_path = request_out / "terminal.json"
        if terminal_path.exists():
            result = read_json(terminal_path)
            if result["outer_identity"] != identity:
                raise ValueError("request terminal identity mismatch")
            verify_file_hashes(result["files"])
        else:
            state_path = request_out / "progress.json"
            state = read_json(state_path) if state_path.exists() else None
            runner.repair_journal_tail(request_out / "attempts.jsonl")
            captured = jsonl(request_out / "attempts.jsonl")
            reservations = jsonl(request_out / "reservations.jsonl")
            if len(reservations) > 3 or len(reservations) < len(captured):
                raise ValueError("generation reservation/journal count mismatch")
            for index, captured_row in enumerate(captured):
                reserved = reservations[index]
                if (reserved["identity"] != identity or reserved["attempt"] != index + 1
                        or reserved["prompt_sha256"] != captured_row["prompt_sha256"]):
                    raise ValueError("generation reservation identity mismatch")
            before = len((request_out / "attempts.jsonl").read_text().splitlines()) if (request_out / "attempts.jsonl").exists() else 0
            # A process may die after the controller writes a terminal error but
            # before the wrapper seals it. Never spend the remaining budget again.
            if len(reservations) > len(captured):
                trace = {"sample_id": record.sample_id, "attempts": captured, "fallback_used": False,
                         "final_origin": "unresolved", "unmatched_reservations": reservations[len(captured):]}
                result = {"predictions": [], "traces": [], "identity": runner.identity([record], backend, active, chosen_bank),
                          "errors": {record.sample_id: {"reason": "interrupted_reserved_call; never regenerate", "trace": trace}}}
            elif state and state["errors"]:
                if state["identity"] != runner.identity([record], backend, active, chosen_bank):
                    raise ValueError("terminal error identity mismatch")
                result = {"predictions": [], "traces": [], "errors": state["errors"], "identity": state["identity"]}
            else:
                reserved_backend = ReservedBackend(backend, request_out / "reservations.jsonl", identity, record.sample_id)
                result = runner.run_records([record], reserved_backend, active, request_out, examples=chosen_bank)
            after = len((request_out / "attempts.jsonl").read_text().splitlines()) if (request_out / "attempts.jsonl").exists() else 0
            fresh_calls += after - before
            files = {str(p.resolve()): sha_file(p) for p in request_out.iterdir() if p.is_file()}
            result = {**result, "outer_identity": identity, "files": files}
            write_json(terminal_path, result)
        predictions.extend(result["predictions"])
        traces.extend(result["traces"])
        errors.update(result["errors"])
        print(json.dumps({"arm": arm, "completed": len(predictions), "processed": index + 1, "total": len(records),
                          "unresolved": len(errors)}), flush=True)
        write_json(out / "partial.predictions.json", predictions)
    requested = {r.sample_id: int(r.target_feedback_level[6]) for r in records}
    validation = validate_export(predictions, requested)
    if validation["valid"]:
        write_json(out / "predictions.json", predictions)
    elif (out / "predictions.json").exists():
        raise ValueError("stale complete export exists for an incomplete run")
    write_json(out / "unresolved.json", errors)
    write_json(out / "traces.json", traces)
    write_json(out / "validation.json", validation)
    result = {"arm": arm, "identity": identity, "predictions": predictions, "unresolved": list(errors),
              "fresh_calls_this_invocation": fresh_calls, "traces": traces, "validation": validation,
              "adapter": tensor_identity, "adapter_active": arm == "C", "source": "fresh_or_exact_resume"}
    write_json(out / "result.json", result)
    return result


def freeze_experiment(repo: Path, config: dict, partitions: dict) -> dict:
    """Seal concrete reviewed sources, exact targets, bank, tokenizer and code."""
    from src.task3.r15_abc_data import assess_arm_data, build_partitions
    from src.task3.r15_abc_training import encode_train_rows
    from src.task3.r15_abc_evaluation import RUBRIC
    require_branch(repo)
    repo = Path(repo).resolve()
    out = repo / config["out"]
    config = {**config, "runtime_out": str(out.resolve())}
    review = read_json(out / "target-review.private.json") if (out / "target-review.private.json").exists() else []
    if len(partitions["comparison_dev"]) != 90 or len(partitions["public_fingerprints"]) != 328:
        raise ValueError("comparison/public population mismatch")
    bank = read_json(out / "bank.private.json") if (out / "bank.private.json").exists() else []
    os.environ["HF_HOME"] = config["hf_cache"]
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    inference = historical_module(out, "task3.inference")
    tokenizer = inference.load_tokenizer(config)
    train = read_json(out / "train-examples.private.json") if (out / "train-examples.private.json").exists() else []
    validation = read_json(out / "checkpoint-examples.private.json") if (out / "checkpoint-examples.private.json").exists() else []
    runtime = historical_module(out, "task3.round15")
    arm_data = assess_arm_data(partitions, review, train, validation, bank, tokenizer, prompt_builder=runtime.build_messages)
    train_audit = val_audit = None
    if arm_data["C"]["status"] == "ready":
        _, train_audit = encode_train_rows(tokenizer, train, 8192)
        _, val_audit = encode_train_rows(tokenizer, validation, 8192)
    inventory = read_json(out / "source-inventory.private.json")
    rebuilt = build_partitions(inventory, partitions["exposure"], config)
    if rebuilt["group_by_id"] != partitions["group_by_id"]:
        raise ValueError("leakage group identity drift")
    for key, original in (("optimizer_train", inventory["optimizer_candidates"]),
                          ("checkpoint_dev", inventory["checkpoint_candidates"] + inventory["optimizer_candidates"]),
                          ("comparison_original", inventory["comparison_sources"])):
        by_id = {r["sample_id"]: r for r in original}
        for r in partitions[key]:
            before = by_id.get(r["sample_id"])
            if before is None or any(r.get(k) != before.get(k) for k in ("code", "statement", "problems", "grading_policy")):
                raise ValueError("partition actual-source binding mismatch")
    files = {}
    for root in ("src/task3", "src/synth", "src/utils"):
        files.update({str(p.resolve()): sha_file(p) for p in (repo / root).rglob("*.py")})
    for p in [repo / "scripts/task3_r15_abc.py", repo / "configs/task3/r15_abc_20261025.yaml",
              *[out / n for n in ("inventory.json", "history-comparison.json", "partitions.json", "bank.private.json",
                                   "target-review.private.json", "train-examples.private.json", "checkpoint-examples.private.json",
                                   "compiler-cache.private.json", "source-inventory.private.json")],
              *[p for p in (out / "vendor").rglob("*.py")]]:
        if p.is_file():
            files[str(p.resolve())] = sha_file(p)
    reference_path = out / "comparison-references.private.json"
    references = read_json(reference_path)
    if {r["sample_id"] for r in references} != {r["sample_id"] for r in partitions["comparison_original"]}:
        raise ValueError("comparison source references must be frozen before generation")
    files[str(reference_path.resolve())] = sha_file(reference_path)
    public_root = Path(config["data_repo"]) / "data/raw/public_test_release"
    public_files = {str(p.resolve()): sha_file(p) for p in public_root.rglob("*") if p.is_file()}
    files.update(public_files)
    # Protect original artifacts actually consumed, including the public cache.
    historic = Path(config["historical_root"])
    for p in (historic / "round15/public-candidate-zero").iterdir():
        if p.is_file():
            files[str(p.resolve())] = sha_file(p)
    value = {"config": config, "files": files, "rubric": RUBRIC, "arm_data": arm_data,
             "public_input_files": public_files,
             "tokenizer": inference.tokenizer_metadata(tokenizer),
             "train_examples_identity": execution_identity(train),
             "token_audit": {"train": train_audit, "validation": val_audit},
             "public_used_for_selection": False,
             "split_sources": {k: len(partitions[k]) for k in ("optimizer_train", "checkpoint_dev", "comparison_original")},
             "public_policy": "observe all feasible arms once; one global recommendation; never submit automatically"}
    value["identity"] = execution_identity(value)
    stable_json(out / "method-freeze.json", value)
    return value


def replay_historical_a(records, config, out, tokenizer):
    """Audit original identity and journal offline; preserve candidate bytes."""
    import shutil
    from types import SimpleNamespace
    source = Path(config["historical_root"]) / "round15/public-candidate-zero"
    historic_run = read_json(source / "run.json")
    bank = read_json(Path(config["historical_root"]) / "round15/train-examples.json")
    runner = historical_module(config["runtime_out"], "task3.round15_runner")
    active = {**historic_run["config"], "implementation_sha256": historic_run["implementation_sha256"],
              "example_bank_sha256": sha_file(Path(config["historical_root"]) / "round15/train-examples.json")}
    backend = SimpleNamespace(tokenizer=tokenizer)
    old = read_json(source / "progress.json")
    if len(old["completed"]) != len(records) or old["errors"]:
        raise ValueError("historical A incomplete")
    if runner.identity(records, backend, active, bank) != old["identity"]:
        raise ValueError("historical A source/payload/config/tokenizer identity mismatch")
    snapshot = read_json(Path(config["runtime_out"]) / "history-comparison.json")
    if any(snapshot["files"][p]["original_sha256"] != h for p, h in historic_run["implementation_sha256"].items()):
        raise ValueError("historical A implementation manifest mismatch")
    out = Path(out)
    replay = out / "historical-replay"
    replay.mkdir(parents=True, exist_ok=True)
    for name in ("progress.json", "attempts.jsonl", "decisions.jsonl"):
        target = replay / name
        if target.exists() and sha_file(target) != sha_file(source / name):
            raise ValueError("historical replay journal drift")
        if not target.exists():
            shutil.copy2(source / name, target)
    result = runner.run_records(records, backend, active, replay, examples=bank)
    validation = validate_export(result["predictions"], {r.sample_id: int(r.target_feedback_level[6]) for r in records})
    if not validation["valid"] or read_json(source / "predictions.json") != result["predictions"]:
        raise ValueError("historical candidate does not match replayed final outputs")
    shutil.copy2(source / "predictions.json", out / "predictions.json")
    write_json(out / "traces.json", result["traces"])
    write_json(out / "unresolved.json", {})
    write_json(out / "validation.json", validation)
    audit = {"source": "historical_replay", "arm": "A", "identity": old["identity"],
             "historical_path": str(source), "predictions_sha256": sha_file(out / "predictions.json"),
             "fresh_calls_this_invocation": 0, "fresh_input_tokens": 0, "fresh_output_tokens": 0,
             "historical_cost": historic_run["attempt_totals"], "historical_wall_s": historic_run["wall_s"],
             "byte_match": True, "adapter_active": False, "validation": validation}
    write_json(out / "result.json", audit)
    return audit


def phase_costs(phase):
    """Journal totals survive resumes; replay never becomes fresh measurement."""
    phase = Path(phase)
    result = read_json(phase / "result.json")
    costs = {"source": result.get("source"), "fresh_generations": 0, "fresh_input_tokens": 0,
             "fresh_output_tokens": 0, "fresh_generation_latency_s": 0., "unknown_output_token_calls": 0}
    if result.get("source") == "historical_replay":
        return {**costs, "historical_cost": result["historical_cost"], "historical_wall_s": result.get("historical_wall_s")}
    for journal in phase.glob("requests/*/attempts.jsonl"):
        for line in journal.read_text().splitlines():
            row = json.loads(line)
            costs["fresh_generations"] += 1
            costs["fresh_input_tokens"] += row.get("input_tokens", 0)
            costs["fresh_output_tokens"] += row.get("output_tokens", 0)
            costs["fresh_generation_latency_s"] += row.get("latency_s", 0.)
            costs["unknown_output_token_calls"] += bool(row.get("token_count_unknown"))
    for reservation in phase.glob("requests/*/reservations.jsonl"):
        charged = jsonl(reservation)
        captured = jsonl(reservation.with_name("attempts.jsonl"))
        if len(charged) > len(captured):
            missing = charged[len(captured):]
            costs["fresh_generations"] += len(missing)
            costs["fresh_input_tokens"] += sum(r["input_tokens"] for r in missing)
            costs["unknown_output_token_calls"] += len(missing)
    costs["generation_count_scope"] = "captured calls plus charged interrupted reservations; interrupted output tokens unknown"
    return costs
