"""Task 4.4: export every result table and figure used in the thesis from ``results/``, with one command.

The tables are rebuilt from the stored summaries (never typed by hand), so a rerun of any experiment
followed by this script refreshes all of them. Each table is written as CSV (full precision) and as
Markdown (rounded, ready to copy); ``--decimal-comma`` writes the Markdown with a decimal comma, as
in the Romanian thesis. Figures are copied under stable names. ``index.md`` lists every asset with
its source file.

Outputs in ``reports/assets/``: tables/*.csv, tables/*.md, figures/*.png, index.md.

Usage::

    python make_report_assets.py
    python make_report_assets.py --decimal-comma
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT  # noqa: E402

log = logging.getLogger("make_report_assets")
RES = ROOT / "results"
SEEDS = [f"seed{i}" for i in range(10)]
NAMES = {"image_only": "Photo, EfficientNet-B0 fine-tuned", "questionnaire_only": "Questionnaire only",
         "fusion_concat": "Fusion concat", "fusion_film": "Fusion FiLM", "fusion_gated": "Fusion gated",
         "fusion_concat_nodrop": "Fusion concat, no dropout", "ensemble_image_q": "Ensemble photo + questionnaire",
         "probe_effb0": "EfficientNet-B0 ImageNet + probe", "probe_vit_in21k": "ViT-B/16 ImageNet-21k + probe",
         "probe_dinov2": "DINOv2 + probe", "probe_panderm_base": "PanDerm-Base + probe",
         "probe_panderm_large": "PanDerm-Large + probe", "probe_dermlip": "DermLIP + probe",
         "fitz_pooled": "Pooled SCIN + Fitzpatrick17k", "fitz_pretrain": "Fitzpatrick17k, then SCIN",
         "nodrop": "Concat, no dropout", "fixed": "Concat, fixed dropout", "randdrop": "Concat, random dropout"}


def ms(mean, sd) -> str:
    return f"{mean:.3f} ± {sd:.3f}"


def arm_table(summary: Path, arms: list[str], metrics: list[str], **where) -> pd.DataFrame:
    d = pd.read_csv(summary)
    d = d[(d["row_type"] == "arm") & np.isclose(d["missing_pct"], 0.0)]
    for col, val in where.items():
        d = d[d[col] == val]
    rows = []
    for a in arms:
        r = {"model": NAMES.get(a, a)}
        for m in metrics:
            x = d[(d["arm"] == a) & (d["metric"] == m)].iloc[0]
            r[m] = ms(x["mean"], x["sd"])
        rows.append(r)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------- tables
def t_e1() -> pd.DataFrame:
    arms = ["image_only", "questionnaire_only", "fusion_concat", "fusion_film", "fusion_gated",
            "fusion_concat_nodrop", "ensemble_image_q"]
    return arm_table(RES / "e1" / "e1_summary.csv", arms, ["macro_f1", "balanced_acc", "ece"])


def t_e2() -> pd.DataFrame:
    d = pd.read_csv(RES / "e2" / "e2_concat_summary.csv")
    d = d[d["row_type"] == "arm"]
    out = d.pivot_table(index="arm", columns="missing_pct", values="mean").loc[["image_only", "nodrop", "fixed", "randdrop"]]
    out.columns = [f"{int(100 * c)}% hidden" for c in out.columns]
    return out.rename(index=NAMES).reset_index(names="model").round(3)


def t_e3() -> pd.DataFrame:
    d = pd.read_csv(RES / "e3" / "e3_by_tone.csv")
    d = d[(d["dataset"] == "scin") & (d["kind"] == "arm") & (d["metric"] == "macro_f1")]
    d = d.assign(col=d["scale"] + " " + d["group"], val=[ms(m, s) for m, s in zip(d["mean"], d["sd"])])
    out = d.pivot(index="arm", columns="col", values="val")
    order = [a for a in NAMES if a in out.index]
    return out.loc[order, ["eFST I-II", "eFST III-IV", "eFST V-VI", "eMST 1-3", "eMST 4-6", "eMST 7-10"]] \
        .rename(index=NAMES).reset_index(names="model")


def t_e4() -> pd.DataFrame:
    d = pd.read_csv(RES / "e4" / "e4_calibration.csv")
    d = d[d["group"].isna()]
    cols = ["T", "ece_before", "ece_after", "aurc", "coverage", "selective_accuracy"]
    g = d.groupby("arm", sort=False)[cols]
    out = pd.DataFrame({c: [ms(m, s) for m, s in zip(g.mean()[c], g.std()[c])] for c in cols}, index=g.mean().index)
    return out.rename(index=NAMES).reset_index(names="model")


def t_e4_ood() -> pd.DataFrame:
    d = pd.read_csv(RES / "e4" / "e4_ood_auroc.csv")
    g = d.groupby(["set", "method"], sort=False)["auroc"]
    out = pd.DataFrame({"auroc": [ms(m, s) for m, s in zip(g.mean(), g.std())]}, index=g.mean().index).reset_index()
    return out.pivot(index="set", columns="method", values="auroc").reset_index()


def t_e5() -> pd.DataFrame:
    arms = ["image_only", "probe_effb0", "probe_vit_in21k", "probe_dinov2", "probe_panderm_base",
            "probe_panderm_large", "probe_dermlip"]
    return arm_table(RES / "e5" / "e5_summary.csv", arms, ["macro_f1", "balanced_acc", "ece"])


def t_e7() -> pd.DataFrame:
    arms = ["image_only", "fitz_pooled", "fitz_pretrain"]
    a = arm_table(RES / "e7" / "e7_summary.csv", arms, ["macro_f1", "balanced_acc"], test_set="test")
    b = arm_table(RES / "e7" / "e7_summary.csv", arms, ["macro_f1"], test_set="fitz_test")
    return a.assign(fitzpatrick17k_macro_f1=b["macro_f1"])


def t_stats() -> pd.DataFrame:
    d = pd.read_csv(RES / "stats" / "contrasts.csv")
    return pd.DataFrame({"family": d["family"], "contrast": d["contrast"], "metric": d["metric"],
                         "mean diff": d["mean"].map(lambda x: f"{x:+.3f}"),
                         "95% t interval": [f"[{lo:+.3f}, {hi:+.3f}]" for lo, hi in zip(d["t_low"], d["t_high"])],
                         "better seeds": d["better_seeds"].astype(str) + "/" + d["n_seeds"].astype(str),
                         "Holm p (family)": d["holm_family"].round(3), "Holm p (all)": d["holm_all"].round(3)})


TABLES = {"e1_questionnaire": (t_e1, "results/e1/e1_summary.csv", "RQ1: photo, questionnaire and fusion (SCIN test)"),
          "e2_missing_answers": (t_e2, "results/e2/e2_concat_summary.csv", "RQ2: macro-F1 by share of hidden answers"),
          "e3_by_tone": (t_e3, "results/e3/e3_by_tone.csv", "RQ3: macro-F1 by skin-tone group"),
          "e4_calibration": (t_e4, "results/e4/e4_calibration.csv", "RQ4: calibration and selective prediction"),
          "e4_ood_detector": (t_e4_ood, "results/e4/e4_ood_auroc.csv", "Task 4.2b: out-of-scope detector AUROC"),
          "e5_encoders": (t_e5, "results/e5/e5_summary.csv", "E5: frozen encoders + linear probe"),
          "e7_extra_data": (t_e7, "results/e7/e7_summary.csv", "E7: extra Fitzpatrick17k training data"),
          "stats_contrasts": (t_stats, "results/stats/contrasts.csv", "Task 4.4: every main contrast, one procedure")}
FIGURES = {"e2_missing_answers.png": "results/e2/e2_curve.png",
           "e3_benefit_by_tone.png": "results/e3/e3_benefit_by_tone.png",
           "e4_risk_coverage.png": "results/e4/e4_risk_coverage.png",
           "e4_abstention_by_tone.png": "results/e4/e4_abstention_by_tone.png",
           "e4_reliability.png": "results/e4/e4_reliability.png",
           "e4_ood_detector.png": "results/e4/e4_ood.png"}


def to_markdown(df: pd.DataFrame, decimal_comma: bool) -> str:
    def cell(v):
        s = f"{v:.3f}" if isinstance(v, float) else str(v)
        return re.sub(r"(?<=\d)\.(?=\d)", ",", s) if decimal_comma else s
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    lines = [head, "|---" * len(df.columns) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "assets")
    ap.add_argument("--decimal-comma", action="store_true", help="Markdown tables with a decimal comma (Romanian)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    (args.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    (args.out_dir / "figures").mkdir(parents=True, exist_ok=True)
    index = ["# Result assets", "", "Generated by `make_report_assets.py` from the stored results; do not edit by hand.",
             "", "| Asset | Source | Content |", "|---|---|---|"]
    for name, (fn, src, title) in TABLES.items():
        df = fn()
        df.to_csv(args.out_dir / "tables" / f"{name}.csv", index=False)
        (args.out_dir / "tables" / f"{name}.md").write_text(f"# {title}\n\n" + to_markdown(df, args.decimal_comma),
                                                             encoding="utf-8")
        index.append(f"| tables/{name}.csv, .md | {src} | {title} |")
    for name, src in FIGURES.items():
        shutil.copyfile(ROOT / src, args.out_dir / "figures" / name)
        index.append(f"| figures/{name} | {src} | figure |")
    (args.out_dir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    log.info("%d tables and %d figures -> %s", len(TABLES), len(FIGURES), args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
