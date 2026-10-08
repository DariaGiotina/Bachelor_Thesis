"""Overall and skin-tone-stratified evaluation.

Macro-F1 is averaged over the classes that occur in the evaluated group's true labels: a class
absent from a group (e.g. no rosacea case in eFST V-VI) has no defined F1 there. Wrong predictions
of an absent class still lower the score, through the recall of the classes that were missed.
Small groups get a bootstrap 95% confidence interval (cases resampled with replacement).
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

NON_TONE_GROUPS = {"ALL", "missing"}


def macro_f1(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(f1_score(y_true, y_pred, labels=np.unique(y_true), average="macro", zero_division=0))


def bootstrap_ci(y_true, y_pred, n_boot: int = 1000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap confidence interval of macro-F1."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    rng = np.random.default_rng(seed)
    n = len(y_true)
    stats = [macro_f1(y_true[i], y_pred[i]) for i in (rng.integers(0, n, n) for _ in range(n_boot))]
    return float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))


def stratified_report(y_true, y_pred, groups, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Macro-F1 (with 95% CI) and balanced accuracy overall and per group (e.g. eFST group)."""
    y_true, y_pred, groups = map(np.asarray, (y_true, y_pred, groups))
    rows = []
    for g in ["ALL", *sorted(set(groups))]:
        m = np.ones(len(y_true), bool) if g == "ALL" else groups == g
        yt, yp = y_true[m], y_pred[m]
        lo, hi = bootstrap_ci(yt, yp, n_boot, seed=seed)
        with warnings.catch_warnings():  # a group may lack some classes; that is expected here
            warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
            bal = balanced_accuracy_score(yt, yp)
        rows.append((g, int(m.sum()), len(np.unique(yt)), macro_f1(yt, yp), lo, hi, bal))
    return pd.DataFrame(rows, columns=["group", "n", "n_classes", "macro_f1", "ci_low", "ci_high", "balanced_acc"])


def max_gap(report: pd.DataFrame, col: str = "macro_f1") -> float:
    """Largest difference between skin-tone groups (the overall row and 'missing' are not tone groups)."""
    g = report[~report.group.isin(NON_TONE_GROUPS)][col]
    return float(g.max() - g.min()) if len(g) > 1 else float("nan")
