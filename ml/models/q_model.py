"""Questionnaire-only baseline (E1 arm 2): a small MLP over the encoded answers and their mask.

Input is ``[q_vec, q_mask]``: ``q_vec`` holds the encoded answers (one-hot, multi-hot and ordinal
features, 0 when a field is missing) and ``q_mask`` has one entry per field (1 = not answered). The
mask is part of the input so the network can tell "answered no" from "not answered"; missing
answers are never imputed. With every field missing the input is all zeros plus an all-ones mask,
so the model can only predict from the class balance it learned: this is the lower bound of what the
questionnaire alone can do.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class QuestionnaireMLP(nn.Module):
    def __init__(self, n_q_features: int, n_q_fields: int, n_classes: int, hidden: int = 64, depth: int = 2,
                 dropout: float = 0.2):
        super().__init__()
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.n_q_features, self.n_q_fields = n_q_features, n_q_fields
        layers, d = [], n_q_features + n_q_fields
        for _ in range(depth):
            layers += [nn.Linear(d, hidden), nn.ReLU(), nn.Dropout(dropout)]
            d = hidden
        self.body = nn.Sequential(*layers)
        self.head = nn.Linear(d, n_classes)

    def forward(self, q_vec: torch.Tensor, q_mask: torch.Tensor) -> torch.Tensor:
        if q_vec.shape[1] != self.n_q_features or q_mask.shape[1] != self.n_q_fields:
            raise ValueError(f"expected {self.n_q_features} features and {self.n_q_fields} mask columns, "
                             f"got {q_vec.shape[1]} and {q_mask.shape[1]}")
        return self.head(self.body(torch.cat([q_vec, q_mask], dim=1).float()))
