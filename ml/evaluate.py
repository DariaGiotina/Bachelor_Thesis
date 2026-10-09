"""Evaluate a predictions CSV: overall and skin-tone-stratified metrics with case-level bootstrap CIs.

Input columns: case_id, split, true_label, pred_label, confidence, eFST, eMST, seed, missing_pct.
Every (split, seed, missing_pct) slice is evaluated separately (a slice is one test of one model);
slices of the same split and missing_pct are then summarised across seeds (mean, sd, min, max of the
point estimates).

Per slice:
* overall macro-F1, balanced accuracy, accuracy and ECE, each with a 95% bootstrap CI (cases resampled);
* per-class precision / recall / F1;
* the same metrics per eFST group (I-II, III-IV, V-VI, missing) and eMST group (1-3, 4-6, 7-10, missing);
* the worst skin-tone group (lowest macro-F1 among tone groups with at least ``--min-group-n`` cases;
  'missing' is not a tone) and the gap between best and worst group;
* risk-coverage table and AURC (accuracy when only the most confident predictions are kept).

Outputs (next to the CSV unless ``--out-dir``): metrics_summary.json, metrics_summary.csv (one row per
slice x scope x group x metric), risk_coverage.csv.

Usage::

    python evaluate.py runs/fusion_seed0/predictions.csv
    python evaluate.py preds_all_seeds.csv --n-boot 2000 --bins 10 --split test
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from skinconcern.metrics import (  # noqa: E402
    NON_TONE_GROUPS, TONE_ORDER, aurc, bootstrap_standard_metrics, efst_group, emst_group,
    per_class_report, risk_coverage)

log = logging.getLogger("evaluate")
REQUIRED = ["case_id", "split", "true_label", "pred_label", "confidence", "eFST", "eMST", "seed", "missing_pct"]
SCALES = {"eFST": efst_group, "eMST": emst_group}


def load_predictions(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"case_id": str, "true_label": str, "pred_label": str})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name} lacks columns {missing}")
    if df[["true_label", "pred_label", "confidence"]].isna().any().any():
        raise ValueError("true_label, pred_label and confidence must not be empty")
    if not df["confidence"].between(0, 1).all():
        raise ValueError("confidence must be a probability in [0, 1]")
    dup = df.duplicated(["split", "seed", "missing_pct", "case_id"])
    if dup.any():
        raise ValueError(f"{int(dup.sum())} duplicate case_id rows within a (split, seed, missing_pct) slice")
    for scale, fn in SCALES.items():
        df[f"{scale}_group"] = df[scale].map(fn)
    return df


def metrics_with_ci(df: pd.DataFrame, args) -> dict:
    """macro-F1, balanced accuracy, accuracy and ECE with case-level bootstrap 95% CIs."""
    return {"n_cases": int(df["case_id"].nunique()),
            **bootstrap_standard_metrics(df, args.bins, args.n_boot, seed=args.boot_seed)}


def worst_group(groups: dict, min_n: int) -> dict:
    """Tone group with the lowest macro-F1 (groups with fewer than min_n cases are not eligible)."""
    eligible = {g: v for g, v in groups.items()
                if g not in NON_TONE_GROUPS and v["n_cases"] >= min_n and not np.isnan(v["macro_f1"]["value"])}
    if not eligible:
        return {"group": None, "reason": f"no tone group with >= {min_n} cases"}
    worst = min(eligible, key=lambda g: eligible[g]["macro_f1"]["value"])
    best = max(eligible, key=lambda g: eligible[g]["macro_f1"]["value"])
    return {"group": worst, "n_cases": eligible[worst]["n_cases"], "macro_f1": eligible[worst]["macro_f1"],
            "best_group": best, "gap_macro_f1": eligible[best]["macro_f1"]["value"] - eligible[worst]["macro_f1"]["value"],
            "excluded_small_groups": sorted(g for g, v in groups.items()
                                            if g not in NON_TONE_GROUPS and v["n_cases"] < min_n)}


def evaluate_slice(df: pd.DataFrame, classes: list[str], args) -> tuple[dict, pd.DataFrame]:
    res = {"overall": metrics_with_ci(df, args),
           "per_class": per_class_report(df["true_label"], df["pred_label"], classes).to_dict("records"),
           "aurc": aurc(df["confidence"], df["true_label"] == df["pred_label"])}
    for scale in SCALES:
        groups = {}
        for g in TONE_ORDER[scale]:
            sub = df[df[f"{scale}_group"] == g]
            if len(sub):
                groups[g] = metrics_with_ci(sub, args)
        res[scale] = {"groups": groups, "worst_group": worst_group(groups, args.min_group_n)}
    rc = risk_coverage(df["confidence"], df["true_label"] == df["pred_label"], df["true_label"], df["pred_label"])
    return res, rc


def flatten(summary: dict) -> pd.DataFrame:
    rows = []
    for key, res in summary["slices"].items():
        split, seed, missing = key.split("|")
        base = {"split": split, "seed": seed, "missing_pct": float(missing)}

        def add(scope, group, block):
            for metric, v in block.items():
                if isinstance(v, dict) and "value" in v:
                    rows.append({**base, "scope": scope, "group": group, "n_cases": block["n_cases"],
                                 "metric": metric, **v})

        add("overall", "ALL", res["overall"])
        for scale in SCALES:
            for g, block in res[scale]["groups"].items():
                add(scale, g, block)
            w = res[scale]["worst_group"]
            if w.get("group"):
                rows.append({**base, "scope": scale, "group": f"worst={w['group']}", "n_cases": w["n_cases"],
                             "metric": "worst_group_macro_f1", **w["macro_f1"]})
                rows.append({**base, "scope": scale, "group": f"{w['best_group']}-{w['group']}", "n_cases": np.nan,
                             "metric": "gap_macro_f1", "value": w["gap_macro_f1"], "ci_low": np.nan, "ci_high": np.nan})
        for pc in res["per_class"]:
            for metric in ("precision", "recall", "f1"):
                rows.append({**base, "scope": "class", "group": pc["class"], "n_cases": pc["support"],
                             "metric": metric, "value": pc[metric], "ci_low": np.nan, "ci_high": np.nan})
        rows.append({**base, "scope": "overall", "group": "ALL", "n_cases": res["overall"]["n_cases"],
                     "metric": "aurc", "value": res["aurc"], "ci_low": np.nan, "ci_high": np.nan})
    return pd.DataFrame(rows)


def across_seeds(flat: pd.DataFrame) -> pd.DataFrame:
    # worst-group and gap rows name a different group per seed, so they are not averaged here;
    # tone groups such as 'I-II' or '1-3' are kept
    keep = flat[flat["scope"].isin(["overall", "eFST", "eMST"]) & ~flat["group"].str.startswith("worst=")
                & (flat["metric"] != "gap_macro_f1")]
    agg = keep.groupby(["split", "missing_pct", "scope", "group", "metric"])["value"].agg(
        n_seeds="count", mean="mean", sd="std", min="min", max="max").reset_index()
    return agg


def summarise(df: pd.DataFrame, args) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    classes = sorted(set(df["true_label"]) | set(df["pred_label"]))
    summary = {"source": str(args.predictions), "n_boot": args.n_boot, "ece_bins": args.bins,
               "min_group_n": args.min_group_n, "classes": classes, "slices": {}}
    rcs = []
    for (split, seed, missing), sub in df.groupby(["split", "seed", "missing_pct"], sort=True):
        key = f"{split}|{seed}|{missing}"
        summary["slices"][key], rc = evaluate_slice(sub, classes, args)
        rcs.append(rc.assign(split=split, seed=seed, missing_pct=missing))
        o = summary["slices"][key]["overall"]
        log.info("%-5s seed %s missing %.2f | n=%d macro-F1 %.3f [%.3f, %.3f] bal-acc %.3f ECE %.3f | worst eFST %s",
                 split, seed, float(missing), o["n_cases"], o["macro_f1"]["value"], o["macro_f1"]["ci_low"],
                 o["macro_f1"]["ci_high"], o["balanced_acc"]["value"], o["ece"]["value"],
                 summary["slices"][key]["eFST"]["worst_group"].get("group"))
    flat = flatten(summary)
    agg = across_seeds(flat)
    summary["across_seeds"] = agg.to_dict("records")
    return summary, flat, pd.concat(rcs, ignore_index=True)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    raise TypeError(type(o))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("predictions", type=Path)
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--split", default=None, help="evaluate only this split (default: all)")
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--boot-seed", type=int, default=0)
    p.add_argument("--bins", type=int, default=15, help="ECE bins")
    p.add_argument("--min-group-n", type=int, default=20, help="minimum cases for a worst-group candidate")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    df = load_predictions(args.predictions)
    if args.split:
        df = df[df["split"] == args.split]
    out = args.out_dir or args.predictions.parent
    out.mkdir(parents=True, exist_ok=True)
    summary, flat, rc = summarise(df, args)
    (out / "metrics_summary.json").write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")
    flat.to_csv(out / "metrics_summary.csv", index=False)
    rc.to_csv(out / "risk_coverage.csv", index=False)
    log.info("wrote metrics_summary.json, metrics_summary.csv, risk_coverage.csv -> %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
