"""Task 4.4: every main contrast of the study in one place, tested the same way.

Each experiment runner already tests its own contrasts. This script recomputes them from the stored
per-seed results, so every reported comparison uses one definition and one multiple-testing rule:

  difference   a - b per split seed (the same test cases for both models within a seed)
  interval     95% t interval over the seeds (the runners' case-bootstrap intervals are copied
               alongside where they exist)
  tests        paired t-test and Wilcoxon signed-rank test over the seeds; Holm correction within
               each family (one research question or experiment) and over all contrasts together
  check        where a runner stored the same contrast, its mean difference and t-test p must agree
               (mean within 1e-4, p within 0.005; otherwise the script stops)

Families: RQ1 questionnaire (E1), RQ2 missing answers (E2), E5 frozen encoders, E7 extra training
data, RQ4 confidence ranking (E4, AURC; lower is better, so the sign is flipped: positive = better),
and the out-of-scope detector (Task 4.2b, AUROC).

Outputs in ``results/stats/``: contrasts.csv, contrasts.md.

Usage::

    python stats_tests.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT  # noqa: E402
from run_e1 import holm  # noqa: E402

log = logging.getLogger("stats_tests")
SEEDS = [f"seed{i}" for i in range(10)]
RES = ROOT / "results"


# ------------------------------------------------------------------------------------- sources
def seed_values(summary: Path, arm: str, metric: str = "macro_f1", missing_pct: float = 0.0,
                **where) -> pd.Series:
    """Per-seed values of one arm from an experiment summary (``arm`` rows)."""
    d = pd.read_csv(summary)
    sel = (d["row_type"] == "arm") & (d["arm"] == arm) & np.isclose(d["missing_pct"], missing_pct)
    if "metric" in d:
        sel &= d["metric"] == metric
    for col, val in where.items():
        sel &= d[col] == val
    if sel.sum() != 1:
        raise ValueError(f"{summary.name}: {sel.sum()} rows for arm={arm} {metric} r={missing_pct} {where}")
    return d.loc[sel, SEEDS].iloc[0].astype(float).set_axis(range(10))


def stored_pair(summary: Path, a: str, b: str, missing_pct: float = 0.0, row_type: str = "paired",
                **where) -> pd.Series | None:
    d = pd.read_csv(summary)
    sel = (d["row_type"] == row_type) & (d["arm"] == a) & (d["versus"] == b) & np.isclose(d["missing_pct"], missing_pct)
    if "metric" in d:
        sel &= d["metric"] == "macro_f1"
    for col, val in where.items():
        sel &= d[col] == val
    return d[sel].iloc[0] if sel.sum() == 1 else None


def e4_aurc(arm: str) -> pd.Series:
    d = pd.read_csv(RES / "e4" / "e4_calibration.csv")
    d = d[(d["arm"] == arm) & d["group"].isna()].astype({"seed": int}).set_index("seed")["aurc"]
    return -d.sort_index()  # negative AURC: higher = better, like every other metric here


def ood_auroc(method: str, set_name: str) -> pd.Series:
    d = pd.read_csv(RES / "e4" / "e4_ood_auroc.csv")
    return d[(d["method"] == method) & (d["set"] == set_name)].set_index("seed")["auroc"].sort_index()


def registry() -> list[dict]:
    """(family, label, a, b, stored runner row) for every main contrast."""
    e1, e2, e5, e7 = (RES / "e1" / "e1_summary.csv", RES / "e2" / "e2_concat_summary.csv",
                      RES / "e5" / "e5_summary.csv", RES / "e7" / "e7_summary.csv")
    photo = seed_values(e1, "image_only")
    out = []

    def add(family, label, a, b, stored=None, metric="macro-F1"):
        out.append({"family": family, "contrast": label, "metric": metric, "a": a, "b": b, "stored": stored})

    for arm, label in (("fusion_concat", "fusion concat"), ("fusion_film", "fusion FiLM"),
                       ("fusion_gated", "fusion gated"), ("fusion_concat_nodrop", "fusion concat, no dropout"),
                       ("ensemble_image_q", "ensemble photo + questionnaire"),
                       ("questionnaire_only", "questionnaire only")):
        add("RQ1 questionnaire (E1)", f"{label} - photo", seed_values(e1, arm), photo,
            stored_pair(e1, arm, "image_only"))
    for arm, label in (("fixed", "fixed answer dropout"), ("randdrop", "random answer dropout")):
        for r in (0.0, 1.0):
            add("RQ2 missing answers (E2)", f"{label} - no dropout, {int(100 * r)}% hidden",
                seed_values(e2, arm, missing_pct=r), seed_values(e2, "nodrop", missing_pct=r),
                stored_pair(e2, arm, "nodrop", r))
    for arm in ("nodrop", "fixed", "randdrop"):
        add("RQ2 missing answers (E2)", f"concat {arm}: 100% - 0% hidden", seed_values(e2, arm, missing_pct=1.0),
            seed_values(e2, arm, missing_pct=0.0), stored_pair(e2, arm, "same arm at r=0", 1.0, "drop_r1_vs_r0"))
    for arm, label in (("probe_effb0", "EfficientNet-B0 ImageNet"), ("probe_vit_in21k", "ViT-B/16 ImageNet-21k"),
                       ("probe_dinov2", "DINOv2"), ("probe_panderm_base", "PanDerm-Base"),
                       ("probe_panderm_large", "PanDerm-Large"), ("probe_dermlip", "DermLIP")):
        add("E5 frozen encoders", f"{label} probe - fine-tuned photo", seed_values(e5, arm), photo,
            stored_pair(e5, arm, "image_only"))
    for arm, label in (("fitz_pooled", "pooled SCIN + Fitzpatrick17k"), ("fitz_pretrain", "Fitzpatrick17k then SCIN")):
        add("E7 extra training data", f"{label} - photo, SCIN test", seed_values(e7, arm, test_set="test"),
            seed_values(e7, "image_only", test_set="test"), stored_pair(e7, arm, "image_only", test_set="test"))
    base = e4_aurc("image_only")
    for arm, label in (("fusion_film", "FiLM fusion"), ("probe_dinov2", "DINOv2 probe"),
                       ("probe_panderm_large", "PanDerm-Large probe"), ("probe_dermlip", "DermLIP probe")):
        add("RQ4 confidence ranking (E4)", f"{label} - photo", e4_aurc(arm), base, metric="AURC reduction")
    for set_name, label in (("scin_ood", "SCIN other conditions"), ("ddi_malignant", "DDI malignant"),
                            ("fitz_out", "Fitzpatrick17k out of scope")):
        add("Out-of-scope detector (4.2b)", f"kNN - max probability, {label}", ood_auroc("knn", set_name),
            ood_auroc("msp", set_name), metric="AUROC")
        add("Out-of-scope detector (4.2b)", f"Mahalanobis - kNN, {label}", ood_auroc("mahalanobis", set_name),
            ood_auroc("knn", set_name), metric="AUROC")
    return out


# ------------------------------------------------------------------------------------- testing
def paired(a: pd.Series, b: pd.Series) -> dict:
    """Mean difference over seeds, 95% t interval, seeds better, paired t and Wilcoxon p."""
    if not a.index.equals(b.index):
        raise ValueError("the two arms do not cover the same seeds")
    d = (a - b).to_numpy(float)
    n, m, sd = len(d), d.mean(), d.std(ddof=1)
    h = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    t_p = stats.ttest_1samp(d, 0).pvalue if sd > 0 else np.nan
    w_p = stats.wilcoxon(d).pvalue if np.any(d != 0) else np.nan
    return {"n_seeds": n, "mean": m, "sd": sd, "t_low": m - h, "t_high": m + h,
            "better_seeds": int((d > 0).sum()), "t_test_p": t_p, "wilcoxon_p": w_p}


def run(tol: float = 1e-4, p_tol: float = 5e-3) -> pd.DataFrame:
    """``p_tol`` is wider than ``tol``: the summaries store per-seed values rounded to 5 decimals, which
    moves p in the fourth decimal when the mean difference is close to 0."""
    rows = []
    for c in registry():
        r = {"family": c["family"], "contrast": c["contrast"], "metric": c["metric"], **paired(c["a"], c["b"])}
        s = c["stored"]
        if s is not None:
            if abs(s["mean"] - r["mean"]) > tol or (pd.notna(s["t_test_p"]) and abs(s["t_test_p"] - r["t_test_p"]) > p_tol):
                raise ValueError(f"{c['contrast']}: stored mean {s['mean']:.5f} / p {s['t_test_p']:.5f} vs "
                                 f"recomputed {r['mean']:.5f} / {r['t_test_p']:.5f}")
            r.update(boot_low=s["ci_low"], boot_high=s["ci_high"], checked=True)
        else:
            r.update(boot_low=np.nan, boot_high=np.nan, checked=False)
        rows.append(r)
    df = pd.DataFrame(rows)
    df["holm_family"] = np.nan
    for _, idx in df.groupby("family", sort=False).groups.items():
        df.loc[idx, "holm_family"] = holm(df.loc[idx, "t_test_p"].tolist())
    df["holm_all"] = holm(df["t_test_p"].tolist())
    return df


def markdown(df: pd.DataFrame) -> str:
    out = ["# Task 4.4: main contrasts, one test procedure", "",
           "Difference a - b per split seed (10 seeds). Interval: 95% t interval over seeds; case bootstrap: the "
           "experiment runner's interval (resampled test cases), where it stored this contrast. p: paired t-test and "
           "Wilcoxon over seeds; Holm within the family and over all contrasts. checked = the runner's stored mean "
           "and t-test p agree with this recomputation (mean within 1e-4, p within 0.005; stored per-seed values are rounded).", ""]
    for fam, d in df.groupby("family", sort=False):
        out += [f"## {fam}", "",
                "| Contrast | metric | mean diff | 95% t interval | case bootstrap | better seeds | t p | Wilcoxon p | "
                "Holm (family) | Holm (all) | checked |", "|---" * 11 + "|"]
        for _, r in d.iterrows():
            boot = f"[{r['boot_low']:+.3f}, {r['boot_high']:+.3f}]" if pd.notna(r["boot_low"]) else "-"
            out.append(f"| {r['contrast']} | {r['metric']} | {r['mean']:+.3f} | [{r['t_low']:+.3f}, {r['t_high']:+.3f}] "
                       f"| {boot} | {r['better_seeds']}/{r['n_seeds']} | {r['t_test_p']:.3f} | {r['wilcoxon_p']:.3f} | "
                       f"{r['holm_family']:.3f} | {r['holm_all']:.3f} | {'yes' if r['checked'] else '-'} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", type=Path, default=RES / "stats")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = run()
    df.to_csv(args.out_dir / "contrasts.csv", index=False)
    (args.out_dir / "contrasts.md").write_text(markdown(df), encoding="utf-8")
    log.info("%d contrasts (%d checked against the runners), %d with Holm (all) < 0.05 -> %s", len(df),
             int(df["checked"].sum()), int((df["holm_all"] < 0.05).sum()), args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
