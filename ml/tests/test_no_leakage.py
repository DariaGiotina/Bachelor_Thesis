import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "splits" / "train_val_test_splits.json"
LABELS = ROOT / "labels" / "scin_labels.csv"
SEEDS = ["0", "1", "2", "3", "4"]


@pytest.fixture(scope="module")
def splits() -> dict:
    return json.loads(SPLITS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def all_ids() -> set:
    return set(pd.read_csv(LABELS, dtype={"case_id": str})["case_id"])


def test_all_five_seeds_present(splits):
    assert sorted(splits) == SEEDS


@pytest.mark.parametrize("seed", SEEDS)
def test_no_case_overlap_between_splits(splits, seed):
    s = {k: set(v) for k, v in splits[seed].items()}
    assert s["train"] & s["val"] == set()
    assert s["train"] & s["test"] == set()
    assert s["val"] & s["test"] == set()


@pytest.mark.parametrize("seed", SEEDS)
def test_no_duplicates_and_full_coverage(splits, seed, all_ids):
    parts = splits[seed]
    flat = parts["train"] + parts["val"] + parts["test"]
    assert len(flat) == len(set(flat)), "a case_id appears twice"
    assert set(flat) == all_ids, "splits do not cover every case exactly once"


@pytest.mark.parametrize("seed", SEEDS)
def test_split_sizes_are_70_15_15(splits, seed):
    n = sum(len(v) for v in splits[seed].values())
    for name, frac in (("train", 0.70), ("val", 0.15), ("test", 0.15)):
        assert abs(len(splits[seed][name]) / n - frac) < 0.01


def test_seeds_give_different_splits(splits):
    tests = {tuple(splits[s]["test"]) for s in SEEDS}
    assert len(tests) == len(SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_duplicate_image_groups_stay_in_one_split(splits, seed):
    """Cases sharing an identical photo must not be divided between splits."""
    dups = pd.read_csv(ROOT / "splits" / "duplicate_image_groups.csv", dtype=str)
    where = {cid: name for name, ids in splits[seed].items() for cid in ids}
    for group, g in dups.groupby("dup_group"):
        assert len({where[c] for c in g["case_id"]}) == 1, f"{group} spans splits"
