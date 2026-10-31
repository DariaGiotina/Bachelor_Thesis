import numpy as np
import timm
import torch

import run_finetune_dinov2 as ft
from data_loading import build_transform, load_config, ROOT
from run_e1 import arm_spec, pairs


def _cfg(pad_mode):
    cfg = load_config(ROOT / "configs" / "base.yaml")
    cfg["data"]["image_size"] = 32
    cfg["data"]["pad_mode"] = pad_mode
    return cfg


def test_black_padding_is_the_default_and_reflect_fills_the_border():
    img = np.full((16, 32, 3), 200, np.uint8)  # landscape: padded above and below
    default = load_config(ROOT / "configs" / "base.yaml")
    default["data"]["image_size"] = 32
    black = build_transform(default, train=False)(image=img)["image"]
    assert torch.equal(black, build_transform(_cfg("constant"), train=False)(image=img)["image"])
    mirrored = build_transform(_cfg("reflect"), train=False)(image=img)["image"]
    assert not torch.allclose(black[:, 0], black[:, 16])           # black band at the top
    assert torch.allclose(mirrored[:, 0], mirrored[:, 16])         # mirrored image: same as the content


def test_head_starts_as_the_linear_probe():
    torch.manual_seed(0)
    vit = timm.create_model("vit_tiny_patch16_224", pretrained=False, num_classes=0)
    x = torch.randn(3, 3, 224, 224)
    with torch.no_grad():
        f = vit(x)
    probe = {"state_dict": {"weight": torch.randn(4, f.shape[1]), "bias": torch.randn(4)},
             "mean": f.mean(0), "std": f.std(0) + 0.5}
    head = torch.nn.Linear(f.shape[1], 4)
    w, b = probe["state_dict"]["weight"], probe["state_dict"]["bias"]
    with torch.no_grad():
        head.weight.copy_(w / probe["std"])
        head.bias.copy_(b - (w / probe["std"]) @ probe["mean"])
        expected = ((f - probe["mean"]) / probe["std"]) @ w.T + b
        assert torch.allclose(head(f), expected, atol=1e-4)


def test_layer_decay_orders_learning_rates():
    vit = timm.create_model("vit_tiny_patch16_224", pretrained=False, num_classes=4)
    groups = ft.param_groups(vit, lr=1e-4, head_lr=1e-3, decay=0.5, weight_decay=0.05)
    lr = {g["name"]: g["lr"] for g in groups}
    n = len(vit.blocks)
    assert lr["head_decay"] == 1e-3
    assert lr["0_decay"] < lr["1_decay"] < lr[f"{n}_decay"] < lr[f"{n + 1}_no_decay"] == 1e-4
    no_decay = {id(p) for g in groups if g["weight_decay"] == 0 for p in g["params"]}
    assert id(vit.pos_embed) in no_decay and id(vit.cls_token) in no_decay
    n_params = sum(len(g["params"]) for g in groups)
    assert n_params == len(list(vit.parameters()))


def test_warmup_then_cosine():
    f = [ft.lr_factor(s, 10, 100) for s in range(100)]
    assert f[0] == 0.1 and f[9] == 1.0 and f[10] == 1.0
    assert all(a >= b for a, b in zip(f[10:], f[11:])) and f[-1] < 0.01


def test_new_arms_are_compared_with_the_app_model():
    arms = ["image_only", "probe_dinov2", "probe_dinov2_reflect", "probe_dinov2_reg", "finetune_dinov2"]
    p = pairs(arms)
    for a in arms[2:]:
        assert (a, "probe_dinov2") in p and (a, "image_only") in p
    assert arm_spec("probe_dinov2_reflect", "efficientnet_b0", "weighted_loss")["dir"].name.endswith("__reflect")
    assert arm_spec("finetune_dinov2", "efficientnet_b0", "weighted_loss")["dir"].name == "constant"


def test_stages_train_head_then_top_blocks():
    vit = timm.create_model("vit_tiny_patch16_224", pretrained=False, num_classes=4)
    ft.set_trainable(vit, 0)
    assert {n for n, p in vit.named_parameters() if p.requires_grad} == {"head.weight", "head.bias"}
    ft.set_trainable(vit, 2)
    on = {n.split(".")[0] + ("." + n.split(".")[1] if n.startswith("blocks.") else "")
          for n, p in vit.named_parameters() if p.requires_grad}
    n = len(vit.blocks)
    assert on == {"head", "norm", f"blocks.{n - 2}", f"blocks.{n - 1}"}
