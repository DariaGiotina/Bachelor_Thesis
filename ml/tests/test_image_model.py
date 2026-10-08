import sys
from pathlib import Path

import pytest
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.image_model import SkinImageBaseline  # noqa: E402

BACKBONES = ["efficientnet_b0", "mobilenetv3_large_100"]


def _trainable_units(m):
    return [n for n, mods in m.units() if any(p.requires_grad for mod in mods for p in mod.parameters())]


@pytest.mark.parametrize("backbone", BACKBONES)
def test_stages_open_the_right_layers(backbone):
    m = SkinImageBaseline(4, backbone, pretrained=False, top_blocks=2)
    head = m.head()
    assert head.out_features == 4
    m.set_stage(1)
    assert _trainable_units(m) == [] and all(p.requires_grad for p in head.parameters())
    m.set_stage(2)
    n_blocks = len(m.net.blocks)
    assert _trainable_units(m) == [f"blocks.{n_blocks - 2}", f"blocks.{n_blocks - 1}", "neck"]
    m.set_stage(3)
    assert all(p.requires_grad for p in m.parameters())
    assert m(torch.randn(2, 3, 224, 224)).shape == (2, 4)


@pytest.mark.parametrize("backbone", BACKBONES)
def test_param_groups_cover_exactly_the_trainable_params(backbone):
    m = SkinImageBaseline(4, backbone, pretrained=False)
    for stage in (1, 2, 3):
        m.set_stage(stage)
        groups = m.get_optimizer_param_groups(1e-3, backbone_lr_mult=0.1)
        ids = [id(p) for g in groups for p in g["params"]]
        assert len(ids) == len(set(ids))
        assert set(ids) == {id(p) for p in m.parameters() if p.requires_grad}
        lrs = {g["name"].split("_")[0]: g["lr"] for g in groups}
        assert lrs["head"] == 1e-3
        if stage > 1:
            assert lrs["backbone"] == pytest.approx(1e-4)
        assert all(g["weight_decay"] == 0 for g in groups if g["name"].endswith("no_decay"))
        torch.optim.AdamW(groups)  # accepted as is


def test_frozen_batchnorm_stays_in_eval_mode():
    m = SkinImageBaseline(4, "efficientnet_b0", pretrained=False)
    m.set_stage(2)
    m.train()
    bns = [(mod, any(p.requires_grad for p in mod.parameters())) for mod in m.modules()
           if isinstance(mod, nn.BatchNorm2d)]
    assert all(not mod.training for mod, trainable in bns if not trainable)
    assert all(mod.training for mod, trainable in bns if trainable)


def test_stage1_does_not_change_backbone_or_bn_stats():
    m = SkinImageBaseline(4, "mobilenetv3_large_100", pretrained=False)
    m.set_stage(1)
    before = {k: v.clone() for k, v in m.net.state_dict().items() if not k.startswith("classifier")}
    opt = torch.optim.AdamW(m.get_optimizer_param_groups(1e-2))
    m.train()
    for _ in range(2):
        loss = m(torch.randn(4, 3, 64, 64)).sum()
        opt.zero_grad()
        loss.backward()
        opt.step()
    after = m.net.state_dict()
    assert all(torch.equal(before[k], after[k]) for k in before)


def test_rejects_other_backbones():
    with pytest.raises(ValueError):
        SkinImageBaseline(4, "resnet18", pretrained=False)


def test_new_head_starts_near_uniform():
    m = SkinImageBaseline(4, "efficientnet_b0", pretrained=False).eval()
    with torch.no_grad():
        probs = m(torch.randn(8, 3, 224, 224)).softmax(1)
    assert torch.allclose(probs, torch.full_like(probs, 0.25), atol=0.05)
