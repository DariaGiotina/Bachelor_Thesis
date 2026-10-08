import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import data_loading as dl  # noqa: E402

CONFIG = ROOT / "configs" / "base.yaml"
HAS_IMAGES = any((ROOT / "data" / "scin" / "images").glob("*.png"))
needs_images = pytest.mark.skipif(not HAS_IMAGES, reason="SCIN images not downloaded")


def test_val_and_test_have_no_augmentation():
    names = [type(t).__name__ for t in dl.build_transform(dl.load_config(CONFIG), train=False).transforms]
    assert names == ["Resize", "Normalize", "ToTensorV2"]
    train = [type(t).__name__ for t in dl.build_transform(dl.load_config(CONFIG), train=True).transforms]
    assert {"HorizontalFlip", "Affine", "ColorJitter"} <= set(train)


@needs_images
def test_item_structure_and_no_nan():
    ds = dl.SCINDataset(CONFIG, "val", seed=0, only_available=True)
    item = ds[0]
    assert set(item) == {"image", "q_vec", "q_mask", "label", "eFST", "case_id", "image_ok"}
    assert item["image"].shape == (3, 224, 224)
    assert item["q_vec"].shape == (40,) and item["q_mask"].shape == (6,)
    assert not torch.isnan(item["q_vec"]).any()


@needs_images
def test_val_is_deterministic_and_train_changes_with_epoch():
    val = dl.SCINDataset(CONFIG, "val", seed=0, only_available=True)
    assert torch.equal(val[0]["image"], val[0]["image"])
    train = dl.SCINDataset(CONFIG, "train", seed=0, only_available=True)
    a = train[0]["image"]
    train.set_epoch(1)
    assert not torch.equal(a, train[0]["image"])
    train.set_epoch(0)
    assert torch.equal(a, train[0]["image"])


def test_cases_stay_in_their_split():
    sets = {s: set(dl.SCINDataset(CONFIG, s, seed=0).case_ids) for s in ("train", "val", "test")}
    assert not (sets["train"] & sets["val"] or sets["train"] & sets["test"] or sets["val"] & sets["test"])
