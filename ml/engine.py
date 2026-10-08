"""Model-agnostic training and evaluation engine.

The engine never looks inside a model. Every batch from ``data_loading.py`` is a dict of tensors
(plus lists of ids); an ``adapt`` callable turns it into the keyword arguments the model needs:

    adapt(batch, training) -> dict          # e.g. {"image": batch["image"]}

so the same functions train a plain CNN (image only) and a late-fusion network (image + questionnaire).
Tensors are moved to the device here; the labels are read from ``batch["label"]``.
"""
from __future__ import annotations

import time
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import balanced_accuracy_score, f1_score

Adapt = Callable[[dict, bool], dict]


def image_only_adapt(batch: dict, training: bool) -> dict:
    """Default adapter: the model takes the image only, as ``model(image=...)``."""
    return {"image": batch["image"]}


def to_device(inputs: dict, device: torch.device) -> dict:
    return {k: (v.to(device, non_blocking=True) if torch.is_tensor(v) else v) for k, v in inputs.items()}


def train_one_epoch(model: nn.Module, loader, loss_fn: nn.Module, optimizer: torch.optim.Optimizer,
                    scaler: torch.amp.GradScaler, device: torch.device, adapt: Adapt = image_only_adapt,
                    amp: bool = True, grad_clip: float | None = 1.0, max_batches: int | None = None) -> float:
    """One pass over the training loader with AMP; returns the mean loss per sample."""
    model.train()
    total, n = 0.0, 0
    use_amp = amp and device.type == "cuda"
    for b, batch in enumerate(loader):
        if max_batches and b >= max_batches:
            break
        inputs, target = to_device(adapt(batch, True), device), batch["label"].to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, enabled=use_amp):
            loss = loss_fn(model(**inputs), target)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        if grad_clip:
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        scaler.step(optimizer)
        scaler.update()
        total, n = total + loss.item() * len(target), n + len(target)
    return total / max(n, 1)


@torch.no_grad()
def evaluate(model: nn.Module, loader, loss_fn: nn.Module, device: torch.device,
             adapt: Adapt = image_only_adapt, amp: bool = True, max_batches: int | None = None) -> dict:
    """Mean loss, macro-F1, balanced accuracy and per-case predictions.

    Per case: true and predicted class index, confidence (maximum softmax probability), eFST, eMST
    (when the batch has them) and case_id, for the evaluation harness (``evaluate.py``).
    """
    model.eval()
    total, n = 0.0, 0
    ys, ps, cf, ef, em, ids, failed = [], [], [], [], [], [], 0
    use_amp = amp and device.type == "cuda"
    for b, batch in enumerate(loader):
        if max_batches and b >= max_batches:
            break
        inputs, target = to_device(adapt(batch, False), device), batch["label"].to(device)
        with torch.autocast(device_type=device.type, enabled=use_amp):
            logits = model(**inputs)
            loss = loss_fn(logits, target)
        total, n = total + loss.item() * len(target), n + len(target)
        ys.append(target.cpu().numpy())
        prob = logits.float().softmax(1)
        conf, pred = prob.max(1)
        ps.append(pred.cpu().numpy())
        cf.append(conf.cpu().numpy())
        ef.append(np.asarray(batch["eFST"]))
        em.append(np.asarray(batch.get("eMST", np.full(len(target), -1))))
        ids.append(np.asarray(batch["case_id"]))
        if "image_ok" in batch:
            failed += int((batch["image_ok"] == 0).sum())
    y, p = np.concatenate(ys), np.concatenate(ps)
    return {
        "loss": total / max(n, 1),
        # macro-F1 over the classes present in the true labels (see skinconcern.metrics)
        "macro_f1": float(f1_score(y, p, labels=np.unique(y), average="macro", zero_division=0)),
        "balanced_acc": float(balanced_accuracy_score(y, p)),
        "n": int(n), "n_image_failed": failed, "y_true": y, "y_pred": p, "confidence": np.concatenate(cf),
        "eFST": np.concatenate(ef), "eMST": np.concatenate(em), "case_id": np.concatenate(ids),
    }


class EarlyStopping:
    """Stops when the monitored score (higher is better) has not improved for ``patience`` epochs."""

    def __init__(self, patience: int = 5, min_delta: float = 0.0):
        self.patience, self.min_delta = patience, min_delta
        self.best, self.best_epoch, self.bad_epochs = -float("inf"), -1, 0

    def step(self, score: float, epoch: int) -> bool:
        """Record a score; returns True if it is a new best (checkpoint now)."""
        if score > self.best + self.min_delta:
            self.best, self.best_epoch, self.bad_epochs = score, epoch, 0
            return True
        self.bad_epochs += 1
        return False

    @property
    def should_stop(self) -> bool:
        return self.bad_epochs >= self.patience


def timed(fn, *args, **kwargs):
    """Run ``fn`` and return (result, seconds)."""
    t0 = time.time()
    out = fn(*args, **kwargs)
    return out, time.time() - t0
