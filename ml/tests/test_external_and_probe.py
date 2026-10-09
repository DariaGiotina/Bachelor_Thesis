import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
import torch.nn as nn
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import external_datasets as ext  # noqa: E402
import foundation_probe as fp  # noqa: E402
from data_loading import load_config  # noqa: E402

LABEL_MAP = ROOT / "labels" / "label_map.yaml"
CFG = load_config(ROOT / "configs" / "base.yaml")
TARGETS = list(CFG["data"]["classes"])


def test_mapper_normalises_and_uses_aliases():
    m = ext.LabelMapper(LABEL_MAP, "fitzpatrick17k", TARGETS)
    assert m("Acne") == ("acne", "mapped")
    assert m("acne vulgaris") == ("acne", "mapped")                       # alias
    assert m("seborrheic-dermatitis") == ("eczema_dermatitis", "mapped")  # '-' read as space
    assert m("melanoma") == (None, "excluded_class")                      # listed, not a target
    assert m("hailey hailey disease") == (None, "unmapped")
    assert m(np.nan) == (None, "unmapped")


def test_aliases_are_per_dataset():
    assert ext.LabelMapper(LABEL_MAP, "ddi", TARGETS)("acne vulgaris") == (None, "unmapped")


def _ddi(tmp_path: Path) -> Path:
    (tmp_path / "images").mkdir()
    Image.new("RGB", (60, 80), (200, 120, 100)).save(tmp_path / "images" / "000001.png")
    (tmp_path / "images" / "000002.png").write_bytes(b"not an image")
    pd.DataFrame({"DDI_ID": [1, 2, 3, 4], "DDI_file": ["000001.png", "000002.png", "000003.png", "000004.png"],
                  "skin_tone": [12, 56, 34, 34], "malignant": [False] * 4,
                  "disease": ["folliculitis", "acne-cystic", "melanoma-in-situ", "eczema-spongiotic-dermatitis"]}
                 ).to_csv(tmp_path / "ddi_metadata.csv")
    return tmp_path


def test_ddi_report_flags_every_row(tmp_path):
    rep = ext.mapping_report("ddi", _ddi(tmp_path), LABEL_MAP, TARGETS).set_index("case_id")
    assert rep.loc["000001", "status"] == "mapped" and rep.loc["000001", "eFST"] == 1
    assert rep.loc["000002", "status"] == "mapped" and rep.loc["000002", "eFST"] == 5   # 56 -> group V-VI
    assert rep.loc["000003", "status"] == "unmapped"
    assert rep.loc["000004", "status"] == "missing_image"


def test_unreadable_image_does_not_break_the_loader(tmp_path):
    ds = ext.DDIDataset(CFG, _ddi(tmp_path), LABEL_MAP)
    assert len(ds) == 2
    items = [ds[i] for i in range(len(ds))]
    assert [int(i["image_ok"]) for i in items] == [1, 0]
    assert items[0]["image"].shape == (3, 224, 224)


class _Fixed(nn.Module):
    def forward(self, image):
        return torch.tensor([[0.0, 3.0, 0.0, 0.0]]).repeat(len(image), 1)


def test_predict_frame_matches_evaluate_format(tmp_path):
    ds = ext.DDIDataset(CFG, _ddi(tmp_path), LABEL_MAP)
    df = ext.predict_frame(_Fixed(), ds, seed=3, device=torch.device("cpu"))
    assert set(["case_id", "split", "true_label", "pred_label", "confidence", "eFST", "eMST", "seed",
                           "missing_pct"]) <= set(df.columns)
    assert (df["pred_label"] == "eczema_dermatitis").all() and (df["split"] == "ddi").all()
    assert df["true_label"].tolist() == ["acne", "acne"] and df["eFST"].tolist() == [1, 5]
    assert np.allclose(df[[f"prob_{c}" for c in TARGETS]].sum(axis=1), 1, atol=1e-5)
    path = tmp_path / "p.csv"
    df.to_csv(path, index=False)
    assert len(ext.harness.load_predictions(path)) == 2
    assert ext.seed_of(Path("img_only_seed4.pt")) == 4


def test_probe_learns_separable_features():
    g = torch.Generator().manual_seed(0)
    y = torch.arange(4).repeat(50)
    x = torch.randn(200, 8, generator=g) * 0.1 + nn.functional.one_hot(y, 8).float() * 3
    probe, f1, _ = fp.train_probe(x, y, x, y, 4, l2=0.0, lr=1e-2, epochs=300, patience=50,
                                  device=torch.device("cpu"), seed=0)
    assert f1 == 1.0 and probe.weight.shape == (4, 8)


def test_local_weights_refuse_wrong_architecture(tmp_path):
    model = nn.Sequential(nn.Linear(4, 4), nn.Linear(4, 2))
    torch.save({"model": {"module.other.weight": torch.zeros(3, 3)}}, tmp_path / "w.pt")
    with pytest.raises(ValueError, match="match"):
        fp._load_local_weights(model, tmp_path / "w.pt")
    torch.save({"state_dict": {f"module.{k}": torch.ones_like(v) for k, v in model.state_dict().items()}},
               tmp_path / "ok.pt")
    fp._load_local_weights(model, tmp_path / "ok.pt")
    assert all(bool((v == 1).all()) for v in model.state_dict().values())


def test_backbone_spec_must_name_a_loader():
    with pytest.raises(ValueError, match="timm:"):
        fp.load_encoder("vit_base_patch16_224")
    assert fp.backbone_tag("open_clip:hf-hub:redlessone/DermLIP_ViT-B-16", None) == \
        "open_clip_hf-hub_redlessone_DermLIP_ViT-B-16"
