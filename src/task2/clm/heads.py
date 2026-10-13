"""CLM projection heads (PyTorch) and the two Task 2 learners on frozen Qwen3-8B embeddings.

(A) NoulModel: CLM's yes/no scoring per label, logit = scale * (cos(S(s), A(c_true)) - cos(S(s), A(c_false))),
    i.e. P(true) of the 2-way softmax CLM uses for `noul` questions. Initialised from a CLM checkpoint and
    fine-tuned with weighted BCE; the encoder stays frozen.
(B) LinearProbe: one logistic regression per label on the context embedding (ablation).
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class Head(nn.Module):
    """hidden -> width -> [width -> width]* -> proj MLP; same parameter names as clm.heads.make_head."""

    def __init__(self, hidden: int, width: int, depth: int = 2, proj: int = 512, activation: str = "gelu",
                 layernorm: bool = False, residual: bool = False):
        super().__init__()
        act = {"gelu": nn.GELU, "relu": nn.ReLU, "silu": nn.SiLU}[activation]
        self.inp = nn.Linear(hidden, width)
        self.hidden = nn.ModuleList(nn.Linear(width, width) for _ in range(depth - 2))
        self.norms = nn.ModuleList((nn.LayerNorm(width) if layernorm else nn.Identity()) for _ in range(depth - 2))
        self.out = nn.Linear(width, proj)
        self.act = act()
        self.residual = residual

    def forward(self, x):
        x = self.act(self.inp(x))
        for lin, nrm in zip(self.hidden, self.norms):
            h = self.act(nrm(lin(x)))
            x = x + h if self.residual else h
        return self.out(x)


def _head_kwargs(cfg: dict, top: dict) -> dict:
    return dict(hidden=int(cfg.get("hidden_size", top.get("hidden_size", 4096))), width=int(cfg["width"]),
                depth=int(cfg["depth"]), proj=int(top.get("projection_dim", cfg.get("projection_dim", 512))),
                activation=cfg.get("activation", "gelu"), layernorm=bool(cfg.get("layernorm", False)),
                residual=bool(cfg.get("residual", False)))


def load_heads(path) -> dict:
    """CLM checkpoint: torch `.pt` (upstream release) or a `heads/` dir with config.json + safetensors (MLX port)."""
    p = Path(path)
    if p.is_dir():
        from safetensors.torch import load_file

        top = json.loads((p / "config.json").read_text(encoding="utf-8"))
        cfg = top["cfg"]
        files = sorted(p.glob("*.safetensors"))
        if not files:
            raise FileNotFoundError(f"no .safetensors in {p}")
        w = load_file(str(files[0]))
        sd = {n: {k[len(n) + 1:]: v for k, v in w.items() if k.startswith(n + ".")}
              for n in ("state_head", "action_head")}
        logit = float(w["logit_scale"].float().reshape(-1)[0])
    else:
        ck = torch.load(p, map_location="cpu", weights_only=True)
        top, cfg = ck, dict(ck["cfg"])
        sd = {"state_head": ck["state_head"], "action_head": ck["action_head"]}
        logit = float(torch.as_tensor(ck["logit_scale"]).float().reshape(-1)[0])
    kw = _head_kwargs(cfg, top)
    heads = {}
    for n in ("state_head", "action_head"):
        h = Head(**kw)
        h.load_state_dict({k: v.float() for k, v in sd[n].items()}, strict=True)
        heads[n] = h.float()
    return {"state": heads["state_head"], "action": heads["action_head"], "logit_scale": logit, "cfg": kw}


class NoulModel(nn.Module):
    def __init__(self, state: Head, action: Head, logit_scale: float):
        super().__init__()
        self.state, self.action = state, action
        self.logit_scale = nn.Parameter(torch.tensor(float(logit_scale)))

    @classmethod
    def from_checkpoint(cls, path) -> "NoulModel":
        h = load_heads(path)
        return cls(h["state"], h["action"], h["logit_scale"])

    def scale(self):
        """exp(logit_scale) clamped at 100. The released CLM logit_scale (~4.613, exp ~ 100.8) already sits above
        the clamp, so the effective scale stays fixed at 100 during fine-tuning (the gradient is zero there)."""
        return self.logit_scale.exp().clamp(max=100.0)  # upstream clamps the InfoNCE scale at 100

    def forward(self, s, c_true, c_false):
        zs = F.normalize(self.state(F.normalize(s, dim=-1)), dim=-1)
        zt = F.normalize(self.action(F.normalize(c_true, dim=-1)), dim=-1)
        zf = F.normalize(self.action(F.normalize(c_false, dim=-1)), dim=-1)
        return self.scale() * ((zs * zt).sum(-1) - (zs * zf).sum(-1))


@dataclass
class TrainConfig:
    epochs: int = 15
    lr: float = 1e-5
    weight_decay: float = 0.01
    batch_size: int = 32
    pos_weight_max: float = 10.0
    train_action_head: bool = True
    seed: int = 42
    device: str = "cpu"


def pos_weights(Y, max_w: float) -> torch.Tensor:
    """Inverse-frequency weight of positives per label, in [1, max_w] (soft labels count fractionally)."""
    Y = torch.as_tensor(Y, dtype=torch.float32)
    pos = Y.sum(0)
    return ((Y.shape[0] - pos) / pos.clamp(min=1.0)).clamp(1.0, max_w)


def train_noul(model: NoulModel, S, C, Y, cfg: TrainConfig, eval_fn=None) -> dict:
    torch.manual_seed(cfg.seed)
    dev = torch.device(cfg.device)
    model.to(dev)
    S_t = torch.as_tensor(S, dtype=torch.float32)
    C_t = torch.as_tensor(C, dtype=torch.float32, device=dev)
    Y_t = torch.as_tensor(Y, dtype=torch.float32)
    n, L, _ = S_t.shape
    pw = pos_weights(Y_t, cfg.pos_weight_max).to(dev)
    model.action.requires_grad_(cfg.train_action_head)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=cfg.lr,
                            weight_decay=cfg.weight_decay)
    gen = torch.Generator().manual_seed(cfg.seed)
    hist: dict = {"loss": [], "eval": [], "best_epoch": None}
    best_score, best_state = float("-inf"), None
    for epoch in range(cfg.epochs):
        model.train()
        total = 0.0
        for b in torch.randperm(n * L, generator=gen).split(cfg.batch_size):
            i, j = b // L, b % L
            y = Y_t[i, j].to(dev)
            jd = j.to(dev)
            logit = model(S_t[i, j].to(dev), C_t[jd, 1], C_t[jd, 0])
            loss = F.binary_cross_entropy_with_logits(logit, y, weight=1 + (pw[jd] - 1) * y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(b)
        hist["loss"].append(total / (n * L))
        if eval_fn is not None:
            score = float(eval_fn(model))
            hist["eval"].append(score)
            if score > best_score:
                best_score, best_state, hist["best_epoch"] = score, copy.deepcopy(model.state_dict()), epoch
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return hist


@torch.no_grad()
def predict_noul(model: NoulModel, S, C, batch_size: int = 256) -> np.ndarray:
    model.eval()
    dev = next(model.parameters()).device
    S_t = torch.as_tensor(S, dtype=torch.float32)
    C_t = torch.as_tensor(C, dtype=torch.float32, device=dev)
    n, L, d = S_t.shape
    if n == 0:
        return np.zeros((0, L), np.float32)
    flat, j_all = S_t.reshape(n * L, d), torch.arange(n * L) % L
    out = []
    for k in range(0, n * L, batch_size):
        j = j_all[k:k + batch_size].to(dev)
        out.append(torch.sigmoid(model(flat[k:k + batch_size].to(dev), C_t[j, 1], C_t[j, 0])).cpu())
    return torch.cat(out).reshape(n, L).numpy()


class LinearProbe:
    def __init__(self, C: float = 1.0, seed: int = 42):
        self.C, self.seed = C, seed
        self.models: list = []

    def fit(self, X, Y) -> "LinearProbe":
        from sklearn.linear_model import LogisticRegression

        Yb = np.asarray(Y) >= 0.5
        self.models = []
        for j in range(Yb.shape[1]):
            col = Yb[:, j]
            if col.all() or not col.any():
                self.models.append(float(col.any()))  # constant: no contrast to learn from
            else:
                self.models.append(LogisticRegression(C=self.C, class_weight="balanced", max_iter=2000,
                                                      random_state=self.seed).fit(X, col))
        return self

    def predict_proba(self, X) -> np.ndarray:
        X = np.asarray(X)
        cols = [np.full(len(X), m, np.float32) if isinstance(m, float) else m.predict_proba(X)[:, 1]
                for m in self.models]
        return np.stack(cols, axis=1).astype(np.float32)


class PrototypicalProbe:
    """Few-shot prototypical metric classifier on frozen L2-normalised embeddings.
    For each label, computes positive prototype (centroid of positive samples)
    and negative prototype (centroid of negative samples).
    Probability is derived from relative cosine similarity: sigmoid(tau * (sim_pos - sim_neg))."""

    def __init__(self, tau: float = 5.0, default_prior: float = 0.05):
        self.tau = float(tau)
        self.default_prior = float(default_prior)
        self.proto_pos = None
        self.proto_neg = None
        self.has_pos = None

    def fit(self, X, Y) -> "PrototypicalProbe":
        X = np.asarray(X, dtype=np.float32)
        X = X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)
        Yb = np.asarray(Y) >= 0.5
        n_labels = Yb.shape[1]
        dim = X.shape[1]

        self.proto_pos = np.zeros((n_labels, dim), dtype=np.float32)
        self.proto_neg = np.zeros((n_labels, dim), dtype=np.float32)
        self.has_pos = np.zeros(n_labels, dtype=bool)

        for j in range(n_labels):
            pos_idx = np.where(Yb[:, j])[0]
            neg_idx = np.where(~Yb[:, j])[0]

            if len(pos_idx) > 0:
                p_pos = X[pos_idx].mean(axis=0)
                self.proto_pos[j] = p_pos / (np.linalg.norm(p_pos) + 1e-12)
                self.has_pos[j] = True

            if len(neg_idx) > 0:
                p_neg = X[neg_idx].mean(axis=0)
                self.proto_neg[j] = p_neg / (np.linalg.norm(p_neg) + 1e-12)
            else:
                self.proto_neg[j] = -self.proto_pos[j]

        return self

    def predict_proba(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        X = X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)
        sim_pos = X @ self.proto_pos.T
        sim_neg = X @ self.proto_neg.T

        logits = self.tau * (sim_pos - sim_neg)
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0)))

        for j in range(len(self.has_pos)):
            if not self.has_pos[j]:
                probs[:, j] = self.default_prior

        return probs.astype(np.float32)


class KNNProbe:
    """k-Nearest Neighbor few-shot classifier with cosine similarity soft voting."""

    def __init__(self, k: int = 5):
        self.k = int(k)
        self.X_train = None
        self.Y_train = None

    def fit(self, X, Y) -> "KNNProbe":
        X = np.asarray(X, dtype=np.float32)
        self.X_train = X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)
        self.Y_train = (np.asarray(Y) >= 0.5).astype(np.float32)
        return self

    def predict_proba(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        X = X / (np.linalg.norm(X, axis=-1, keepdims=True) + 1e-12)
        sim = X @ self.X_train.T
        k = min(self.k, len(self.X_train))

        topk_idx = np.argsort(-sim, axis=1)[:, :k]

        probs = np.zeros((len(X), self.Y_train.shape[1]), dtype=np.float32)
        for i in range(len(X)):
            sims = sim[i, topk_idx[i]]
            weights = np.maximum(sims, 0.0) + 1e-6
            weights /= weights.sum()
            probs[i] = weights @ self.Y_train[topk_idx[i]]

        return probs
