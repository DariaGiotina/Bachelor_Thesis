"""Image-only baseline with staged fine-tuning (timm EfficientNet-B0 or MobileNetV3).

timm builds both families from the same parts, which this module relies on:

    EfficientNet-B0:  conv_stem, bn1, blocks[0..6], conv_head, bn2, global_pool, classifier
    MobileNetV3-L:    conv_stem, bn1, blocks[0..6], global_pool, conv_head, norm_head, act2, flatten, classifier

The backbone is seen as an ordered list of units, bottom to top:
``stem`` (conv_stem + bn1), ``blocks.0`` ... ``blocks.K`` (one unit per stage of ``blocks``) and
``neck`` (the pretrained layers between the last block and the classifier: conv_head + bn2 for
EfficientNet, conv_head + norm_head for MobileNetV3). ``classifier`` is the new, randomly
initialised head.

Stages (``set_stage``):
    1  head only (backbone frozen)
    2  head + neck + the top ``top_blocks`` units of ``blocks``
    3  everything

Frozen BatchNorm layers are kept in eval mode, so their running statistics (learned on ImageNet)
are not overwritten by batches they are not trained on.
"""
from __future__ import annotations

import timm
import torch
import torch.nn as nn

SUPPORTED = ("efficientnet", "mobilenetv3")
_NECK_NAMES = ("conv_head", "bn2", "norm_head")


class SkinImageBaseline(nn.Module):
    def __init__(self, num_classes: int, backbone: str = "efficientnet_b0", pretrained: bool = True,
                 top_blocks: int = 2, drop_rate: float = 0.2):
        super().__init__()
        if not backbone.startswith(SUPPORTED):
            raise ValueError(f"backbone must be an EfficientNet or MobileNetV3 timm model, got {backbone!r}")
        # timm replaces the ImageNet classifier with a new Linear(num_features, num_classes)
        self.net = timm.create_model(backbone, pretrained=pretrained, num_classes=num_classes, drop_rate=drop_rate)
        # timm's default init for these models scales the head by its fan-out (= num_classes), which gives
        # large initial logits (start loss ~4.5 instead of ~ln(num_classes)); start from near-uniform outputs
        head = self.net.get_classifier()
        nn.init.normal_(head.weight, std=0.01)
        nn.init.zeros_(head.bias)
        self.backbone_name = backbone
        n_blocks = len(self.net.blocks)
        if not 0 <= top_blocks <= n_blocks:
            raise ValueError(f"top_blocks must be in [0, {n_blocks}]")
        self.top_blocks = top_blocks
        self.stage = 3
        self.set_stage(1)

    # ---------------------------------------------------------------------------- structure
    def units(self) -> list[tuple[str, list[nn.Module]]]:
        """Backbone units from bottom to top (the classifier is not included)."""
        out = [("stem", [self.net.conv_stem, self.net.bn1])]
        out += [(f"blocks.{i}", [b]) for i, b in enumerate(self.net.blocks)]
        neck = [getattr(self.net, n) for n in _NECK_NAMES if hasattr(self.net, n)]
        out.append(("neck", [m for m in neck if any(True for _ in m.parameters())]))
        return out

    def head(self) -> nn.Module:
        return self.net.get_classifier()

    def trainable_units(self, stage: int) -> list[str]:
        names = [n for n, _ in self.units()]
        if stage == 1:
            return []
        if stage == 2:
            blocks = [n for n in names if n.startswith("blocks.")]
            return (blocks[len(blocks) - self.top_blocks:] if self.top_blocks else []) + ["neck"]
        if stage == 3:
            return names
        raise ValueError("stage must be 1, 2 or 3")

    # ------------------------------------------------------------------------------- stages
    def set_stage(self, stage: int) -> None:
        """Set requires_grad for the given fine-tuning stage."""
        open_units = set(self.trainable_units(stage))
        for p in self.net.parameters():
            p.requires_grad = False
        for p in self.head().parameters():
            p.requires_grad = True
        for name, modules in self.units():
            if name in open_units:
                for m in modules:
                    for p in m.parameters():
                        p.requires_grad = True
        self.stage = stage
        self.train(self.training)  # re-apply the BatchNorm mode

    def train(self, mode: bool = True):
        super().train(mode)
        if mode:  # frozen BatchNorm keeps its ImageNet statistics
            for m in self.net.modules():
                if isinstance(m, nn.modules.batchnorm._BatchNorm) and not any(
                        p.requires_grad for p in m.parameters(recurse=False)):
                    m.eval()
        return self

    def get_optimizer_param_groups(self, base_lr: float, backbone_lr_mult: float = 0.1,
                                   weight_decay: float = 0.01) -> list[dict]:
        """Parameter groups for AdamW: head at ``base_lr``, unfrozen backbone at ``base_lr * backbone_lr_mult``.

        Biases and normalisation weights (1-D tensors) get no weight decay. Frozen parameters are left
        out, so the optimizer only holds what is trained in the current stage.
        """
        head_ids = {id(p) for p in self.head().parameters()}
        groups: dict[tuple[str, bool], list[nn.Parameter]] = {}
        for p in self.net.parameters():
            if not p.requires_grad:
                continue
            part = "head" if id(p) in head_ids else "backbone"
            groups.setdefault((part, p.ndim > 1), []).append(p)
        out = []
        for (part, decay), params in sorted(groups.items()):
            out.append({"params": params, "lr": base_lr * (1.0 if part == "head" else backbone_lr_mult),
                        "weight_decay": weight_decay if decay else 0.0, "name": f"{part}_{'decay' if decay else 'no_decay'}"})
        return out

    def n_trainable(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # ------------------------------------------------------------------------------ forward
    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.net(image)
