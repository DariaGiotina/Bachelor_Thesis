"""Loss functions for the imbalanced SCIN categories: class-weighted cross-entropy or focal loss."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def class_weights(labels: np.ndarray, n_classes: int) -> torch.Tensor:
    """Inverse-frequency weights, normalised so a perfectly balanced set gives weight 1."""
    counts = np.bincount(labels, minlength=n_classes).astype(np.float32)
    return torch.tensor(counts.sum() / (n_classes * np.maximum(counts, 1)))


class FocalLoss(nn.Module):
    """Focal loss (Lin et al., 2017): cross-entropy scaled by (1 - p_t)^gamma.

    Easy, confident examples contribute little, so training concentrates on hard and rare ones.
    ``weight`` holds optional per-class weights (alpha). Like ``nn.CrossEntropyLoss(weight=...)``,
    the weighted mean divides by the sum of the weights of the targets, so with ``gamma = 0`` the two
    losses are identical.
    """

    def __init__(self, gamma: float = 2.0, weight: torch.Tensor | None = None):
        super().__init__()
        self.gamma = gamma
        self.register_buffer("weight", weight)

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        logits = logits.float()
        logp = F.log_softmax(logits, dim=1).gather(1, target.unsqueeze(1)).squeeze(1)
        loss = -((1 - logp.exp()) ** self.gamma) * logp
        if self.weight is None:
            return loss.mean()
        w = self.weight[target]
        return (loss * w).sum() / w.sum()


def build_loss(loss_type: str, labels: np.ndarray, n_classes: int, device: torch.device,
               focal_gamma: float = 2.0) -> nn.Module:
    w = class_weights(labels, n_classes).to(device)
    if loss_type == "weighted_ce":
        return nn.CrossEntropyLoss(weight=w)
    if loss_type == "focal":
        return FocalLoss(focal_gamma, w).to(device)
    raise ValueError(f"loss_type must be 'weighted_ce' or 'focal', got {loss_type!r}")
