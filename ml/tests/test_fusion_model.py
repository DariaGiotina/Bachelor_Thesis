import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from models.fusion_model import FUSIONS, LateFusionNet  # noqa: E402

NQ, NM = 8, 3


def _net(fusion="concat", backbone="efficientnet_b0"):
    torch.manual_seed(0)
    return LateFusionNet(4, NQ, NM, backbone, fusion, pretrained=False)


def _inputs(n=2):
    return torch.randn(n, 3, 224, 224), torch.rand(n, NQ), torch.zeros(n, NM)


@pytest.mark.parametrize("fusion", FUSIONS)
def test_output_shape_and_missing_questionnaire(fusion):
    m = _net(fusion).eval()
    img, _, _ = _inputs()
    assert m(img, *_inputs()[1:]).shape == (2, 4)
    # no questionnaire given == every field missing (zeros + all-ones mask), as in training
    assert torch.allclose(m(img), m(img, torch.zeros(2, NQ), torch.ones(2, NM)))
    with pytest.raises(ValueError):
        m(img, torch.zeros(2, NQ))


@pytest.mark.parametrize("fusion", FUSIONS)
def test_stage_one_trains_only_new_layers(fusion):
    m = _net(fusion)
    m.set_stage(1)
    assert not any(p.requires_grad for p in m.image.parameters())
    assert all(p.requires_grad for mod in m.new_modules() for p in mod.parameters())
    m.set_stage(3)
    assert all(p.requires_grad for p in m.parameters())


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_param_groups_cover_exactly_the_trainable_params(stage):
    m = _net("gated")
    m.set_stage(stage)
    groups = m.get_optimizer_param_groups(1e-3, backbone_lr_mult=0.1)
    ids = [id(p) for g in groups for p in g["params"]]
    assert len(ids) == len(set(ids)) == sum(p.requires_grad for p in m.parameters())
    new_ids = {id(p) for mod in m.new_modules() for p in mod.parameters()}
    for g in groups:
        assert g["lr"] == (1e-3 if all(id(p) in new_ids for p in g["params"]) else 1e-4)


def test_frozen_backbone_is_unchanged_by_stage_one_training():
    m = _net("concat")
    m.set_stage(1)
    m.train()
    before = {k: v.clone() for k, v in m.image.state_dict().items()}
    opt = torch.optim.AdamW(m.get_optimizer_param_groups(1e-2)[0]["params"] + m.get_optimizer_param_groups(1e-2)[-1]["params"])
    img, q, mask = _inputs(4)
    nn.functional.cross_entropy(m(img, q, mask), torch.tensor([0, 1, 2, 3])).backward()
    opt.step()
    after = m.image.state_dict()
    assert all(torch.equal(before[k], after[k]) for k in before)  # weights and BatchNorm statistics


def test_film_starts_as_image_only():
    m = _net("film").eval()
    img, q, mask = _inputs()
    assert torch.allclose(m(img, q, mask), m(img, torch.zeros_like(q), torch.ones_like(mask)))


def test_gate_values_are_shares():
    m = _net("gated").eval()
    g = m.gate_values(*_inputs())
    assert g.shape == (2,) and bool(((g > 0) & (g < 1)).all())
    with pytest.raises(ValueError):
        _net("concat").gate_values(*_inputs())


def test_mobilenet_backbone_and_state_dict_round_trip():
    m = _net("concat", "mobilenetv3_large_100").eval()
    m2 = _net("concat", "mobilenetv3_large_100")
    m2.load_state_dict(m.state_dict())
    m2.eval()
    img, q, mask = _inputs()
    assert torch.allclose(m(img, q, mask), m2(img, q, mask))


def test_unknown_fusion_is_rejected():
    with pytest.raises(ValueError):
        LateFusionNet(4, NQ, NM, fusion="attention", pretrained=False)
