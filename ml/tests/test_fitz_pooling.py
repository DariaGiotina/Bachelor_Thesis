"""E7 helpers: Fitzpatrick17k duplicate grouping, grouped folds and the pooled training dataset."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "splits"))
import make_fitzpatrick_splits as mfs  # noqa: E402
import run_fitz_pooling as rfp  # noqa: E402


def test_hamming_matrix_counts_differing_bits():
    rows = np.packbits(np.array([[0] * 16, [1] + [0] * 15, [1] * 16], dtype=np.uint8), axis=1)
    d = mfs.hamming_matrix(rows)
    assert d[0, 1] == 1 and d[0, 2] == 16 and d[1, 2] == 15 and (np.diag(d) == 0).all()


def test_linked_pairs_use_hash_or_cosine():
    ham = np.array([[0, 5, 90], [5, 0, 90], [90, 90, 0]])
    cos = np.array([[1, 0.1, 0.95], [0.1, 1, 0.2], [0.95, 0.2, 1]])
    assert mfs.linked_pairs(ham, cos, max_hash=10, min_cos=0.9) == [(0, 1), (0, 2)]


def test_group_ids_chain_links():
    g = mfs.group_ids(5, [(0, 1), (1, 2), (3, 4)])
    assert g[0] == g[1] == g[2] and g[3] == g[4] and g[0] != g[3]


def test_test_folds_keep_groups_together():
    rng = np.random.default_rng(0)
    groups = np.repeat(np.arange(60), 3)
    labels = np.repeat(rng.integers(0, 3, 60), 3)
    mask = mfs.test_folds(labels, groups, seed=1)
    for g in np.unique(groups):
        assert len(set(mask[groups == g])) == 1
    assert 0.1 < mask.mean() < 0.3
    assert not np.array_equal(mask, mfs.test_folds(labels, groups, seed=2))


def test_fitz_folds_are_disjoint(tmp_path):
    csv = tmp_path / "s.csv"
    pd.DataFrame({"md5hash": ["a", "b", "c"], "test_seed0": [1, 0, 0]}).to_csv(csv, index=False)
    train, test = rfp.fitz_folds(0, csv)
    assert train == {"b", "c"} and test == {"a"}
    with pytest.raises(KeyError):
        rfp.fitz_folds(3, csv)


class _Part(torch.utils.data.Dataset):
    def __init__(self, tag, n):
        self.tag, self.n, self.classes, self.labels, self.epoch = tag, n, ["x", "y"], np.zeros(n, int), 0

    def set_epoch(self, e):
        self.epoch = e

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        return (self.tag, i)


def test_pooled_dataset_indexes_every_part_once():
    a, b = _Part("scin", 3), _Part("fitz", 2)
    pooled = rfp.PooledDataset([a, b])
    assert len(pooled) == 5 and len(pooled.labels) == 5
    assert [pooled[i] for i in range(5)] == [("scin", 0), ("scin", 1), ("scin", 2), ("fitz", 0), ("fitz", 1)]
    pooled.set_epoch(4)
    assert a.epoch == b.epoch == 4


def test_fitz_train_view_matches_scin_item_shape(tmp_path):
    from PIL import Image

    img = tmp_path / "x.png"
    Image.new("RGB", (40, 30), (200, 120, 90)).save(img)
    cfg = {"data": {"classes": ["acne", "other"], "image_size": 32},
           "normalize": {"mean": [0.5] * 3, "std": [0.5] * 3},
           "augment": {"horizontal_flip": {"p": 0.5},
                       "affine": {"p": 0.5, "translate_percent": 0.05, "scale": [0.9, 1.1], "rotate": 10},
                       "color_jitter": {"p": 0.5, "brightness": 0.1, "contrast": 0.1, "saturation": 0.1, "hue": 0.01}}}
    rows = pd.DataFrame({"image_path": [img, tmp_path / "missing.png"], "label": ["other", "acne"], "eFST": [5, pd.NA]})
    ds = rfp.FitzpatrickTrainView(cfg, rows, seed=0, n_q=7, n_m=3)
    item, bad = ds[0], ds[1]
    assert item["image"].shape == (3, 32, 32) and item["label"] == 1 and item["eFST"] == 5
    assert item["q_vec"].sum() == 0 and item["q_mask"].sum() == 3 and item["case_id"] < 0
    assert bad["image_ok"] == 0 and bad["eFST"] == -1
    assert torch.equal(ds[0]["image"], item["image"])  # same epoch -> same augmentation draw
