"""Derive one primary skin-concern category per SCIN case.

For each ``case_id`` the weighted SCIN condition strings are mapped to target
categories via ``label_map.yaml`` and their weights are summed per category. The
category with the largest summed weight becomes ``primary_label`` if that weight
reaches ``min_weight``; ties and weaker cases become ``excluded``.

Writes ``scin_labels.csv`` (case_id, primary_label, top_weight, eFST, eMST) and
``class_counts_by_tone.csv`` (categories x eFST / eMST groups).

Usage::

    python labels/build_labels.py
    python labels/build_labels.py --min-weight 0.5 --mst-pool india
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_scin as audit  # noqa: E402  (reuses eFST / eMST derivation)

log = logging.getLogger("build_labels")
KEY = audit.KEY


def load_map(path: Path, min_weight: float | None = None) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    classes = list(cfg["classes"])
    lookup: dict[str, str] = {}
    for cls, names in cfg["mapping"].items():
        if cls not in classes:
            raise ValueError(f"mapping uses unknown category '{cls}'")
        for name in names:
            key = name.strip().casefold()
            if lookup.setdefault(key, cls) != cls:
                raise ValueError(f"'{name}' is mapped to more than one category")
    if cfg["unmapped_class"] not in classes:
        raise ValueError("unmapped_class must be one of the defined categories")
    cfg["classes"], cfg["lookup"] = classes, lookup
    if min_weight is not None:
        cfg["min_weight"] = min_weight
    if not 0 < float(cfg["min_weight"]) <= 1:
        raise ValueError("min_weight must be in (0, 1]")
    return cfg


def assign_label(weights: dict, cfg: dict) -> tuple[str, float, list[str]]:
    """Return (primary_label, top_weight, unmapped_strings) for one case."""
    excluded = "excluded"
    totals: dict[str, float] = {}
    unmapped: list[str] = []
    for name, w in weights.items():
        cls = cfg["lookup"].get(str(name).strip().casefold())
        if cls is None:
            unmapped.append(name)
            cls = cfg["unmapped_class"]
        totals[cls] = totals.get(cls, 0.0) + float(w)
    if not totals:
        return excluded, np.nan, unmapped
    # `excluded` weight competes too, so a mostly-excluded case is not forced into a target.
    best = max(totals.values())
    winners = [c for c, v in totals.items() if np.isclose(v, best)]
    if len(winners) > 1 or best < cfg["min_weight"]:
        return excluded, round(best, 4), unmapped
    return winners[0], round(best, 4), unmapped


def derive_labels(df: pd.DataFrame, cfg: dict, mst_pool: str) -> tuple[pd.DataFrame, pd.Series]:
    parsed = df[audit.WEIGHTED_LABEL_COL].map(audit._parse_dict)
    results = parsed.map(lambda d: assign_label(d, cfg))
    unmapped = pd.Series([u for r in results for u in r[2]], dtype=object).value_counts()
    out = pd.DataFrame({
        "primary_label": results.map(lambda r: r[0]),
        "top_weight": results.map(lambda r: r[1]).clip(upper=1.0),
        "eFST": df["_efst"].astype("Int64"),
        "eMST": df[f"_emst_{mst_pool}"].astype("Int64"),
        "eFST_group": df["_efst_group"],
        "eMST_group": df[f"_emst_{mst_pool}_group"],
    }, index=df.index)
    return out, unmapped


def counts_by_tone(labels: pd.DataFrame, classes: list[str]) -> pd.DataFrame:
    frames = []
    for scale, col in (("eFST", "eFST_group"), ("eMST", "eMST_group")):
        ct = pd.crosstab(labels[col].fillna("missing"), labels["primary_label"])
        ct = ct.reindex(columns=classes, fill_value=0)
        ct["total"] = ct.sum(axis=1)
        ct.insert(0, "tone_scale", scale)
        ct.index.name = "tone_group"
        frames.append(ct.reset_index())
    return pd.concat(frames, ignore_index=True)[["tone_scale", "tone_group", *classes, "total"]]


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data-dir", type=Path, default=ROOT / "data" / "scin")
    p.add_argument("--label-map", type=Path, default=here / "label_map.yaml")
    p.add_argument("--out-dir", type=Path, default=here)
    p.add_argument("--min-weight", type=float, default=None, help="override label_map.yaml")
    p.add_argument("--mst-pool", choices=["us", "india"], default="us")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_map(args.label_map, args.min_weight)
    cases, raw = audit.load(args.data_dir)
    # Case-level integrity: one row per case_id, so all weights of a case stay together.
    df = audit.derive(audit.merge(cases, raw))

    labels, unmapped = derive_labels(df, cfg, args.mst_pool)
    if not labels.index.is_unique:
        raise ValueError("case_id is not unique in derived labels")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["primary_label", "top_weight", "eFST", "eMST"]
    labels[cols].reset_index().to_csv(args.out_dir / "scin_labels.csv", index=False)
    table = counts_by_tone(labels, cfg["classes"])
    table.to_csv(args.out_dir / "class_counts_by_tone.csv", index=False)

    dist = labels["primary_label"].value_counts()
    log.info("min_weight=%.2f mst_pool=%s cases=%d", cfg["min_weight"], args.mst_pool, len(labels))
    for cls in cfg["classes"]:
        log.info("  %-18s %5d", cls, int(dist.get(cls, 0)))
    log.info("raw strings not in label_map (-> %s): %d distinct, %d mentions",
             cfg["unmapped_class"], len(unmapped), int(unmapped.sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
