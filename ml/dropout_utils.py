"""Modality and answer dropout for the questionnaire branch (Task 3.4, RQ2 / E2).

During training, answers are hidden at random so the fusion model learns to cope with a
questionnaire that is partly or fully unanswered. A hidden answer is never imputed: its feature
columns are set to 0 and its mask bit is set to 1 ("missing"), exactly as for an answer the user
skipped. The model therefore cannot tell a hidden answer from a naturally missing one.

Three training modes (``--q_dropout`` in ``train.py`` and ``run_fusion.py``):

  none    no answers hidden in training (control arm)
  fixed   fixed rates from ``configs/base.yaml``: the whole questionnaire hidden with
          ``train.p_modality_drop`` and each field with ``train.p_field_drop`` (the E1 setting)
  random  per-batch sampled rate: for every training batch a field-drop rate p is drawn uniformly
          from [``answer_dropout.p_field_low``, ``answer_dropout.p_field_high``] (default 0-100%),
          each field of each case is hidden with probability p, and the whole questionnaire of a
          case is hidden with probability ``answer_dropout.p_full``. Sampling p per batch exposes the
          model to every level of missingness, from complete to empty questionnaires, instead of
          one fixed level.

Evaluation always uses a fixed rate r (``train.eval_missing_rates``) and a seeded generator, so
every model sees the same hidden answers.
"""
from __future__ import annotations

import torch

MODES = ("none", "fixed", "random")


def field_index(q_cols: list[str], m_cols: list[str]) -> list[torch.Tensor]:
    """For each mask column m__<field>, the indices of its feature columns f__<field>__*."""
    out = []
    for m in m_cols:
        field = m.split("__", 1)[1]
        out.append(torch.tensor([i for i, c in enumerate(q_cols) if c.split("__")[1] == field]))
    return out


def apply_answer_dropout(q_vec: torch.Tensor, q_mask: torch.Tensor, p_field: float, p_full: float,
                         fields: list[torch.Tensor], gen: torch.Generator | None = None):
    """Hide whole questionnaire fields: zero their features and set their mask bits to 1.

    Each case loses its whole questionnaire with probability ``p_full``; otherwise each field is
    hidden independently with probability ``p_field``. ``fields[j]`` holds the feature columns of
    mask column j (see ``field_index``). The inputs are not modified. Random draws are made in a
    fixed order (whole questionnaire first, then one draw per field), so a seeded generator gives
    the same hidden answers for the same batches.
    """
    q_vec, q_mask = q_vec.clone(), q_mask.clone()
    n = q_vec.size(0)
    whole = torch.rand(n, generator=gen) < p_full
    for j, cols in enumerate(fields):
        drop = whole | (torch.rand(n, generator=gen) < p_field)
        q_vec[drop.nonzero().squeeze(1).unsqueeze(1), cols.unsqueeze(0)] = 0.0
        q_mask[drop, j] = 1.0
    return q_vec, q_mask


def sample_p_field(low: float = 0.0, high: float = 1.0, gen: torch.Generator | None = None) -> float:
    """One field-drop rate drawn uniformly from [low, high] (one draw per training batch)."""
    if not 0.0 <= low <= high <= 1.0:
        raise ValueError(f"need 0 <= low <= high <= 1, got low={low}, high={high}")
    return low + (high - low) * torch.rand(1, generator=gen).item()


def training_rates(mode: str, cfg: dict) -> dict:
    """Dropout settings of a training mode, read from the ``train`` and ``answer_dropout`` config blocks."""
    if mode not in MODES:
        raise ValueError(f"q_dropout must be one of {MODES}, got {mode!r}")
    tc, ad = cfg["train"], cfg.get("answer_dropout", {})
    if mode == "none":
        return {"mode": mode, "p_full": 0.0, "p_field": 0.0}
    if mode == "fixed":
        return {"mode": mode, "p_full": tc["p_modality_drop"], "p_field": tc["p_field_drop"]}
    return {"mode": mode, "p_full": ad.get("p_full", 0.1),
            "p_field_low": ad.get("p_field_low", 0.0), "p_field_high": ad.get("p_field_high", 1.0)}


def make_dropout_adapt(fields: list[torch.Tensor], rates: dict, p_field_eval: float = 0.0, seed: int = 0):
    """Batch -> model kwargs for the fusion model.

    Training: answers hidden according to ``rates`` (``training_rates``); in mode ``random`` a new
    field-drop rate is drawn for every batch. Evaluation: each field hidden with ``p_field_eval``
    (nothing else), with a generator seeded by ``seed``.
    """
    gen = torch.Generator().manual_seed(seed)
    mode = rates["mode"]

    def adapt(batch: dict, training: bool) -> dict:
        q_vec, q_mask = batch["q_vec"], batch["q_mask"]
        if not training:
            pf, pfull = p_field_eval, 0.0
        elif mode == "random":
            pf, pfull = sample_p_field(rates["p_field_low"], rates["p_field_high"], gen), rates["p_full"]
        else:
            pf, pfull = rates["p_field"], rates["p_full"]
        if pf > 0 or pfull > 0:
            q_vec, q_mask = apply_answer_dropout(q_vec, q_mask, pf, pfull, fields, gen)
        return {"image": batch["image"], "q_vec": q_vec, "q_mask": q_mask}

    return adapt
