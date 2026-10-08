"""Evaluation metrics for imbalanced, skin-tone-stratified skin-concern classification.

Conventions
-----------
* Labels are class names or integers; ``true_label`` / ``pred_label`` arrays of equal length.
* Macro-F1 is averaged over the classes present in ``true_label`` of the evaluated set (or over an
  explicit ``labels`` list). A class absent from a skin-tone group has no defined F1 there; wrong
  predictions of it still lower the score through the recall of the classes that were missed.
* ``confidence`` is the maximum softmax probability of a prediction.
* Bootstrap confidence intervals resample **cases** (``case_id``) with replacement and keep all rows
  of a drawn case, so rows of the same case are never treated as independent.
"""
from __future__ import annotations

import warnings
from contextlib import contextmanager
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, classification_report, f1_score

NON_TONE_GROUPS = {"ALL", "missing"}
EFST_GROUPS = {1: "I-II", 2: "I-II", 3: "III-IV", 4: "III-IV", 5: "V-VI", 6: "V-VI"}
TONE_ORDER = {"eFST": ["I-II", "III-IV", "V-VI", "missing"], "eMST": ["1-3", "4-6", "7-10", "missing"]}


@contextmanager
def _quiet():
    """Silence sklearn warnings that are expected when a (bootstrap) sample lacks some classes."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="y_pred contains classes not in y_true")
        warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
        yield


# ------------------------------------------------------------------------------ skin-tone groups
def efst_group(v) -> str:
    """Fitzpatrick type 1-6 -> I-II / III-IV / V-VI; anything else -> missing."""
    try:
        return EFST_GROUPS.get(int(v), "missing")
    except (TypeError, ValueError):
        return "missing"


def emst_group(v) -> str:
    """Monk tone 1-10 -> 1-3 / 4-6 / 7-10; anything else -> missing."""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return "missing"
    return "1-3" if 1 <= v <= 3 else "4-6" if 4 <= v <= 6 else "7-10" if 7 <= v <= 10 else "missing"


# ----------------------------------------------------------------------- classification metrics
def macro_f1(true_label, pred_label, labels=None) -> float:
    t, p = np.asarray(true_label), np.asarray(pred_label)
    if len(t) == 0:
        return float("nan")
    with _quiet():
        return float(f1_score(t, p, labels=np.unique(t) if labels is None else labels,
                              average="macro", zero_division=0))


def balanced_accuracy(true_label, pred_label) -> float:
    """Mean recall over the classes present in ``true_label``."""
    t, p = np.asarray(true_label), np.asarray(pred_label)
    if len(t) == 0:
        return float("nan")
    with _quiet():
        return float(balanced_accuracy_score(t, p))


def per_class_report(true_label, pred_label, labels) -> pd.DataFrame:
    """Precision, recall, F1 and support for every class in ``labels`` (0 where undefined)."""
    with _quiet():
        rep = classification_report(true_label, pred_label, labels=list(labels), output_dict=True, zero_division=0)
    rows = [{"class": str(c), **{k: rep[str(c)][k] for k in ("precision", "recall", "f1-score", "support")}}
            for c in labels]
    return pd.DataFrame(rows).rename(columns={"f1-score": "f1"})


# ------------------------------------------------------------------------------------ calibration
def expected_calibration_error(confidence, correct, n_bins: int = 15) -> float:
    """ECE: |accuracy - mean confidence| per equal-width confidence bin, weighted by bin size."""
    conf, corr = np.asarray(confidence, float), np.asarray(correct, float)
    if len(conf) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(corr[m].mean() - conf[m].mean())
    return float(ece)


def reliability_table(confidence, correct, n_bins: int = 15) -> pd.DataFrame:
    """Per-bin counts, mean confidence and accuracy (for a reliability diagram)."""
    conf, corr = np.asarray(confidence, float), np.asarray(correct, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        rows.append({"bin_low": edges[b], "bin_high": edges[b + 1], "n": int(m.sum()),
                     "mean_confidence": float(conf[m].mean()) if m.any() else np.nan,
                     "accuracy": float(corr[m].mean()) if m.any() else np.nan})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------ selective prediction
def risk_coverage(confidence, correct, true_label=None, pred_label=None,
                  coverages=np.linspace(0.1, 1.0, 10)) -> pd.DataFrame:
    """Accuracy (and macro-F1) when only the most confident predictions are kept.

    Coverage c keeps the ceil(c * n) most confident cases; the rest would be abstained on (e.g. the
    app says "not sure, please consult a professional"). Risk = 1 - accuracy. The confidence
    threshold is the lowest confidence still kept.
    """
    conf, corr = np.asarray(confidence, float), np.asarray(correct, float)
    order = np.argsort(-conf, kind="stable")
    rows = []
    for c in coverages:
        k = max(1, int(np.ceil(c * len(conf))))
        keep = order[:k]
        row = {"coverage": float(c), "n_kept": k, "threshold": float(conf[keep].min()),
               "accuracy": float(corr[keep].mean()), "risk": float(1 - corr[keep].mean())}
        if true_label is not None and pred_label is not None:
            row["macro_f1"] = macro_f1(np.asarray(true_label)[keep], np.asarray(pred_label)[keep])
        rows.append(row)
    return pd.DataFrame(rows)


def aurc(confidence, correct) -> float:
    """Area under the risk-coverage curve over all coverages (lower is better)."""
    conf, corr = np.asarray(confidence, float), np.asarray(correct, float)
    if len(conf) == 0:
        return float("nan")
    order = np.argsort(-conf, kind="stable")
    risks = 1 - np.cumsum(corr[order]) / np.arange(1, len(conf) + 1)
    return float(risks.mean())


# -------------------------------------------------------------------------------------- bootstrap
def bootstrap_ci(df: pd.DataFrame, metric: Callable[[pd.DataFrame], float], case_col: str = "case_id",
                 n_boot: int = 1000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    """Point estimate and percentile (1 - alpha) CI of ``metric(df)``, resampling cases.

    Cases are drawn with replacement; every row of a drawn case is kept (a case drawn twice
    contributes its rows twice). Samples where the metric is undefined (NaN) are skipped.
    """
    point = metric(df)
    if len(df) == 0:
        return point, float("nan"), float("nan")
    codes, uniques = pd.factorize(df[case_col])
    rows_of = pd.Series(np.arange(len(df))).groupby(codes).apply(np.asarray).to_list()
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(n_boot):
        drawn = rng.integers(0, len(uniques), len(uniques))
        sample = df.iloc[np.concatenate([rows_of[i] for i in drawn])]
        v = metric(sample)
        if not np.isnan(v):
            stats.append(v)
    if not stats:
        return point, float("nan"), float("nan")
    return point, float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))


def _fast_metrics(t: np.ndarray, p: np.ndarray, conf: np.ndarray, k: int, n_bins: int) -> tuple:
    """macro-F1, balanced accuracy, accuracy, ECE from integer-coded labels (same definitions as above)."""
    cm = np.bincount(t * k + p, minlength=k * k).reshape(k, k)
    tp, support, predicted = np.diag(cm), cm.sum(1), cm.sum(0)
    present = support > 0
    f1 = 2 * tp[present] / (support[present] + predicted[present])
    correct = (t == p).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    b = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, n_bins - 1)
    n_b = np.bincount(b, minlength=n_bins)
    gap = np.abs(np.bincount(b, correct, n_bins) - np.bincount(b, conf, n_bins))
    return f1.mean(), (tp[present] / support[present]).mean(), correct.mean(), gap.sum() / max(len(t), 1) if n_b.sum() else np.nan


FAST_NAMES = ("macro_f1", "balanced_acc", "accuracy", "ece")


def bootstrap_standard_metrics(df: pd.DataFrame, n_bins: int = 15, n_boot: int = 1000, alpha: float = 0.05,
                               seed: int = 0, case_col: str = "case_id") -> dict[str, dict]:
    """Point estimate (sklearn) and case-level bootstrap CI (fast numpy path) for macro-F1, balanced
    accuracy, accuracy and ECE. Equivalent to ``bootstrap_ci`` with ``frame_metrics`` but much faster."""
    point = {name: fn(df) for name, fn in frame_metrics(n_bins).items()}
    if len(df) == 0:
        return {n: {"value": point[n], "ci_low": np.nan, "ci_high": np.nan} for n in FAST_NAMES}
    classes = sorted(set(df["true_label"]) | set(df["pred_label"]))
    code = {c: i for i, c in enumerate(classes)}
    t = df["true_label"].map(code).to_numpy()
    p = df["pred_label"].map(code).to_numpy()
    conf = df["confidence"].to_numpy(float)
    codes, uniques = pd.factorize(df[case_col])
    rng = np.random.default_rng(seed)
    if len(uniques) == len(df):  # one row per case: resample rows directly
        draws = (rng.integers(0, len(df), len(df)) for _ in range(n_boot))
    else:
        rows_of = pd.Series(np.arange(len(df))).groupby(codes).apply(np.asarray).to_list()
        draws = (np.concatenate([rows_of[i] for i in rng.integers(0, len(uniques), len(uniques))])
                 for _ in range(n_boot))
    stats = np.array([_fast_metrics(t[i], p[i], conf[i], len(classes), n_bins) for i in draws])
    lo, hi = np.nanquantile(stats, alpha / 2, axis=0), np.nanquantile(stats, 1 - alpha / 2, axis=0)
    return {n: {"value": point[n], "ci_low": float(lo[j]), "ci_high": float(hi[j])} for j, n in enumerate(FAST_NAMES)}


# ---------------------------------------------------------- metrics on a predictions DataFrame
def frame_metrics(n_bins: int = 15) -> dict[str, Callable[[pd.DataFrame], float]]:
    """Metric functions on a predictions frame (columns true_label, pred_label, confidence)."""
    return {
        "macro_f1": lambda d: macro_f1(d["true_label"], d["pred_label"]),
        "balanced_acc": lambda d: balanced_accuracy(d["true_label"], d["pred_label"]),
        "accuracy": lambda d: float((d["true_label"] == d["pred_label"]).mean()) if len(d) else float("nan"),
        "ece": lambda d: expected_calibration_error(d["confidence"], d["true_label"] == d["pred_label"], n_bins),
    }


# ------------------------------------------------------- compact report used by train.py
def stratified_report(true_label, pred_label, groups, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Macro-F1 (with 95% case bootstrap CI) and balanced accuracy overall and per group.

    One row per case is assumed (each position is its own case).
    """
    df = pd.DataFrame({"true_label": np.asarray(true_label), "pred_label": np.asarray(pred_label),
                       "group": np.asarray(groups)})
    df["case_id"] = np.arange(len(df))
    f1 = frame_metrics()["macro_f1"]
    rows = []
    for g in ["ALL", *sorted(set(df["group"]))]:
        sub = df if g == "ALL" else df[df["group"] == g]
        point, lo, hi = bootstrap_ci(sub, f1, n_boot=n_boot, seed=seed)
        rows.append((g, len(sub), sub["true_label"].nunique(), point, lo, hi,
                     balanced_accuracy(sub["true_label"], sub["pred_label"])))
    return pd.DataFrame(rows, columns=["group", "n", "n_classes", "macro_f1", "ci_low", "ci_high", "balanced_acc"])


def max_gap(report: pd.DataFrame, col: str = "macro_f1") -> float:
    """Largest difference between skin-tone groups (the overall row and 'missing' are not tone groups)."""
    g = report[~report.group.isin(NON_TONE_GROUPS)][col]
    return float(g.max() - g.min()) if len(g) > 1 else float("nan")
