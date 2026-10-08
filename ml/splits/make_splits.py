"""Create case-level 70/15/15 train/val/test splits for seeds 0-4.

Every row of ``scin_labels.csv`` is one ``case_id`` (all images of a case share it), and the
split is made on ``case_id`` only, so a case can never appear in more than one split. The
split is stratified on ``primary_label`` x eFST group (I-II, III-IV, V-VI, missing) in two
steps: train vs. rest (70/30), then rest into val and test (50/50).

Strata with too few cases to split are merged into a per-label stratum, then into one
``rare`` stratum, so stratification never fails.

Writes ``train_val_test_splits.json`` ({seed: {train, val, test}}) and ``split_summary.csv``.

Usage::

    python splits/make_splits.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (0, 1, 2, 3, 4)
FRACTIONS = {"train": 0.70, "val": 0.15, "test": 0.15}
MIN_STRATUM = 4  # a stratum must survive two stratified splits (>= 2 cases per side)
EFST_GROUPS = {1: "I-II", 2: "I-II", 3: "III-IV", 4: "III-IV", 5: "V-VI", 6: "V-VI"}

log = logging.getLogger("make_splits")


def load_cases(path: Path) -> pd.DataFrame:
    # dtype=str keeps the 64-bit case_id exact.
    df = pd.read_csv(path, dtype={"case_id": str})
    if df["case_id"].isna().any() or df["case_id"].duplicated().any():
        raise ValueError("case_id must be non-null and unique: one row per case")
    df["eFST_group"] = pd.to_numeric(df["eFST"], errors="coerce").map(EFST_GROUPS).fillna("missing")
    return df[["case_id", "primary_label", "eFST_group"]]


def build_strata(df: pd.DataFrame) -> pd.Series:
    """primary_label x eFST_group, with rare strata merged so every stratum has >= MIN_STRATUM."""
    s = df["primary_label"] + "|" + df["eFST_group"]
    small = s.map(s.value_counts()) < MIN_STRATUM
    s = s.where(~small, df["primary_label"] + "|other")
    small = s.map(s.value_counts()) < MIN_STRATUM
    return s.where(~small, "rare")


def split_once(df: pd.DataFrame, strata: pd.Series, seed: int) -> dict[str, list[str]]:
    ids = df["case_id"]
    train, rest = train_test_split(
        ids, test_size=1 - FRACTIONS["train"], stratify=strata, random_state=seed)
    rest_strata = strata.loc[rest.index]
    # the rest is halved; merge strata that are too small to halve again
    small = rest_strata.map(rest_strata.value_counts()) < 2
    rest_strata = rest_strata.where(~small, "rare")
    if (rest_strata.value_counts() < 2).any():
        rest_strata = None
    val, test = train_test_split(
        rest, test_size=FRACTIONS["test"] / (FRACTIONS["val"] + FRACTIONS["test"]),
        stratify=rest_strata, random_state=seed)
    return {"train": sorted(train), "val": sorted(val), "test": sorted(test)}


def check(splits: dict[str, list[str]], all_ids: set[str]) -> None:
    sets = {k: set(v) for k, v in splits.items()}
    if any(len(sets[k]) != len(splits[k]) for k in sets):
        raise AssertionError("duplicate case_id inside a split")
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        if sets[a] & sets[b]:
            raise AssertionError(f"case_id overlap between {a} and {b}")
    if set().union(*sets.values()) != all_ids:
        raise AssertionError("splits do not cover every case_id exactly once")


def summarise(df: pd.DataFrame, all_splits: dict[int, dict[str, list[str]]]) -> pd.DataFrame:
    rows = []
    lookup = df.set_index("case_id")
    for seed, splits in all_splits.items():
        for name, ids in splits.items():
            sub = lookup.loc[ids]
            counts = sub.groupby(["primary_label", "eFST_group"]).size().rename("n_cases").reset_index()
            counts["pct_of_split"] = (100 * counts["n_cases"] / len(sub)).round(2)
            counts.insert(0, "split", name)
            counts.insert(0, "seed", seed)
            rows.append(counts)
    return pd.concat(rows, ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--labels", type=Path, default=ROOT / "labels" / "scin_labels.csv")
    p.add_argument("--out-dir", type=Path, default=here)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    df = load_cases(args.labels)
    strata = build_strata(df)
    log.info("cases=%d strata=%d (rare merged: %d cases)",
             len(df), strata.nunique(), int((strata == "rare").sum()))

    all_ids = set(df["case_id"])
    all_splits = {}
    for seed in SEEDS:
        splits = split_once(df, strata, seed)
        check(splits, all_ids)
        all_splits[seed] = splits
        log.info("seed %d: train=%d val=%d test=%d", seed,
                 len(splits["train"]), len(splits["val"]), len(splits["test"]))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "train_val_test_splits.json").write_text(
        json.dumps({str(s): v for s, v in all_splits.items()}), encoding="utf-8")
    summarise(df, all_splits).to_csv(args.out_dir / "split_summary.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
