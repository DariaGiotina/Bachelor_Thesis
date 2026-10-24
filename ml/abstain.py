"""E4 / Task 4.2: threshold abstention ("uncertain, see a professional") and its fairness by skin tone.

Rule: the model answers only when its calibrated confidence (largest class probability after
temperature scaling) is at least tau; otherwise it abstains. tau is chosen on the validation split
of each seed so that a fixed share of validation cases is kept (the target coverage, default 80%),
then applied unchanged to the test split. Fixing the coverage, not tau, makes models comparable:
every model may abstain on the same share of cases, so the question is only whether it abstains on
the right cases, and equally often for every skin-tone group.

Per group (eFST, eMST) on test:
  coverage            share of cases answered (1 - abstention rate)
  abstention rate     share of cases the model declines
  selective accuracy  accuracy on the answered cases
  abstention precision share of declined cases that would have been wrong (a useful abstention)
  accuracy            accuracy on all cases (no abstention), for reference
Confidence intervals: case bootstrap within each seed, rows of all seeds pooled (the same resamples
for every group, so group differences are paired).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

METRICS = ("coverage", "abstention_rate", "selective_accuracy", "abstention_precision", "accuracy")


def choose_tau(val_confidence: np.ndarray, target_coverage: float = 0.8) -> float:
    """Confidence threshold that keeps ``target_coverage`` of the validation cases."""
    if not 0 < target_coverage <= 1:
        raise ValueError(f"target_coverage must be in (0, 1], got {target_coverage}")
    return float(np.quantile(np.asarray(val_confidence, float), 1 - target_coverage))


def selective(correct: np.ndarray, answered: np.ndarray) -> dict:
    correct, answered = np.asarray(correct, bool), np.asarray(answered, bool)
    n, k = len(correct), int(answered.sum())
    return {"n": n,
            "coverage": k / n if n else np.nan,
            "abstention_rate": 1 - k / n if n else np.nan,
            "selective_accuracy": correct[answered].mean() if k else np.nan,
            "abstention_precision": (~correct[~answered]).mean() if n - k else np.nan,
            "accuracy": correct.mean() if n else np.nan}


def _boot_index(seeds: np.ndarray, n_boot: int, rng: np.random.Generator) -> list[np.ndarray]:
    groups = [np.flatnonzero(seeds == s) for s in np.unique(seeds)]
    return [np.concatenate([g[rng.integers(0, len(g), len(g))] for g in groups]) for _ in range(n_boot)]


def _cluster_index(ids: np.ndarray, n_boot: int, rng: np.random.Generator) -> list[np.ndarray]:
    """Resample whole clusters (e.g. one image scored by every seed's model) with all their rows."""
    _, inv = np.unique(ids, return_inverse=True)
    order = np.argsort(inv, kind="stable")
    rows = np.split(order, np.flatnonzero(np.diff(inv[order])) + 1)
    k = len(rows)
    return [np.concatenate([rows[j] for j in rng.integers(0, k, k)]) for _ in range(n_boot)]


def group_report(df: pd.DataFrame, group_col: str, groups: list[str], contrasts: list[tuple[str, str]],
                 n_boot: int = 1000, seed: int = 0, cluster: str | None = None) -> pd.DataFrame:
    """Selective metrics per group and paired group differences, pooled over seeds, bootstrap CIs.

    ``df`` needs columns seed, correct, answered and ``group_col``. By default cases are resampled
    within each seed (SCIN: every seed has its own test split). With ``cluster`` the resampling unit
    is that column (use ``case_id`` when the same cases are scored by every seed, as on an external
    set), so repeated rows of one case do not count as independent evidence.
    """
    rng = np.random.default_rng(seed)
    corr, ans = df["correct"].to_numpy(bool), df["answered"].to_numpy(bool)
    grp = df[group_col].to_numpy(object)
    idx = (_cluster_index(df[cluster].to_numpy(), n_boot, rng) if cluster
           else _boot_index(df["seed"].to_numpy(), n_boot, rng))

    def stats(sel):
        out = {}
        for g in ["ALL"] + groups:
            m = sel if g == "ALL" else sel[grp[sel] == g]
            out[g] = selective(corr[m], ans[m])
        return out

    point = stats(np.arange(len(df)))
    boots = [stats(i) for i in idx]
    rows = []
    for g in ["ALL"] + groups:
        for met in METRICS:
            vals = np.array([b[g][met] for b in boots], float)
            lo, hi = np.nanpercentile(vals, [2.5, 97.5]) if np.isfinite(vals).any() else (np.nan, np.nan)
            rows.append({"scale": group_col, "group": g, "metric": met, "value": point[g][met],
                         "ci_low": lo, "ci_high": hi, "n_cases": point[g]["n"]})
    for a, b in contrasts:
        for met in METRICS:
            vals = np.array([x[a][met] - x[b][met] for x in boots], float)
            lo, hi = np.nanpercentile(vals, [2.5, 97.5]) if np.isfinite(vals).any() else (np.nan, np.nan)
            rows.append({"scale": group_col, "group": f"{a} - {b}", "metric": met,
                         "value": point[a][met] - point[b][met], "ci_low": lo, "ci_high": hi,
                         "n_cases": point[a]["n"] + point[b]["n"]})
    return pd.DataFrame(rows)
