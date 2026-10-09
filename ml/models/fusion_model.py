"""Photo + questionnaire fusion with an explicit missing-answer indicator (E1 arm 3).

The image branch is ``SkinImageBaseline`` in feature mode (pooled CNN features, no classifier), so the
fusion model reuses the staged fine-tuning of the image baseline unchanged: ``set_stage(1|2|3)``
opens the same backbone units, frozen BatchNorm keeps its ImageNet statistics, and
``get_optimizer_param_groups`` puts the unfrozen backbone at ``base_lr * backbone_lr_mult``. The
questionnaire branch and the fusion layers are new, so they train in every stage at ``base_lr``.

The questionnaire branch embeds ``[q_vec, q_mask]`` with dense layers. ``q_mask`` (1 = field not
answered) is part of the input, so a missing answer is visible to the model instead of being imputed;
a missing questionnaire is zero features plus an all-ones mask, exactly as in training.

Fusion variants (``fusion=``):
  concat  late fusion: [image features, questionnaire embedding] -> classifier head
  gated   gated multimodal unit (Arevalo et al., 2017): both inputs are projected to a shared size,
          and a gate computed from both decides per dimension how much comes from each
          (h = z * tanh(W_i f) + (1 - z) * tanh(W_q e), z = sigmoid(W_z [f, e])); the model can lean on
          the photo when the mask says the answers are missing
  film    FiLM-style conditioning (Perez et al., 2018): the questionnaire scales and shifts every image
          feature, f' = f * (1 + gamma(e)) + beta(e); gamma and beta start at 0, so training starts
          from the image-only behaviour
"""
from __future__ import annotations

import torch
import torch.nn as nn

from models.image_model import SkinImageBaseline

FUSIONS = ("concat", "gated", "film")


class QuestionnaireEncoder(nn.Module):
    """Dense embedding of [q_vec, q_mask]."""

    def __init__(self, n_q_features: int, n_q_fields: int, hidden: int = 64, depth: int = 2, dropout: float = 0.1):
        super().__init__()
        layers, d = [], n_q_features + n_q_fields
        for _ in range(depth):
            layers += [nn.Linear(d, hidden), nn.ReLU(), nn.Dropout(dropout)]
            d = hidden
        self.net, self.out_dim = nn.Sequential(*layers), d

    def forward(self, q_vec: torch.Tensor, q_mask: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([q_vec, q_mask], dim=1))


class LateFusionNet(nn.Module):
    def __init__(self, num_classes: int, n_q_features: int, n_q_fields: int, backbone: str = "efficientnet_b0",
                 fusion: str = "concat", pretrained: bool = True, top_blocks: int = 2, drop_rate: float = 0.2,
                 q_hidden: int = 64, q_depth: int = 2, q_dropout: float = 0.1, fused_dim: int = 256,
                 head_dropout: float = 0.2):
        super().__init__()
        if fusion not in FUSIONS:
            raise ValueError(f"fusion must be one of {FUSIONS}, got {fusion!r}")
        self.fusion, self.n_q_features, self.n_q_fields = fusion, n_q_features, n_q_fields
        self.image = SkinImageBaseline(0, backbone, pretrained, top_blocks, drop_rate)  # pooled features
        self.backbone_name = backbone
        self.q_encoder = QuestionnaireEncoder(n_q_features, n_q_fields, q_hidden, q_depth, q_dropout)
        f_dim, e_dim = self.image.num_features, self.q_encoder.out_dim
        if fusion == "concat":
            head_in = f_dim + e_dim
        elif fusion == "gated":
            self.proj_image, self.proj_q = nn.Linear(f_dim, fused_dim), nn.Linear(e_dim, fused_dim)
            self.gate = nn.Linear(f_dim + e_dim, fused_dim)
            head_in = fused_dim
        else:  # film
            self.film = nn.Linear(e_dim, 2 * f_dim)
            nn.init.zeros_(self.film.weight)  # gamma = beta = 0 at the start: image-only behaviour
            nn.init.zeros_(self.film.bias)
            head_in = f_dim
        self.classifier = nn.Linear(head_in, num_classes)
        nn.init.normal_(self.classifier.weight, std=0.01)  # near-uniform start, as in the image baseline
        nn.init.zeros_(self.classifier.bias)
        self.head_dropout = nn.Dropout(head_dropout)
        self.set_stage(1)

    # ------------------------------------------------------------------------------ staging
    def new_modules(self) -> list[nn.Module]:
        """Everything that is not the pretrained backbone (trained in every stage)."""
        return [m for n, m in self.named_children() if n != "image"]

    @property
    def stage(self) -> int:
        return self.image.stage

    def set_stage(self, stage: int) -> None:
        self.image.set_stage(stage)  # backbone units of this stage
        for m in self.new_modules():
            for p in m.parameters():
                p.requires_grad = True

    def get_optimizer_param_groups(self, base_lr: float, backbone_lr_mult: float = 0.1,
                                   weight_decay: float = 0.01) -> list[dict]:
        """New layers at ``base_lr``, unfrozen backbone at ``base_lr * backbone_lr_mult``; frozen params left out.

        Biases and normalisation weights (1-D tensors) get no weight decay.
        """
        new_ids = {id(p) for m in self.new_modules() for p in m.parameters()}
        groups: dict[tuple[str, bool], list[nn.Parameter]] = {}
        for p in self.parameters():
            if p.requires_grad:
                part = "head" if id(p) in new_ids else "backbone"
                groups.setdefault((part, p.ndim > 1), []).append(p)
        return [{"params": ps, "lr": base_lr * (1.0 if part == "head" else backbone_lr_mult),
                 "weight_decay": weight_decay if decay else 0.0, "name": f"{part}_{'decay' if decay else 'no_decay'}"}
                for (part, decay), ps in sorted(groups.items())]

    def n_trainable(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    # ------------------------------------------------------------------------------ forward
    def forward(self, image: torch.Tensor, q_vec: torch.Tensor | None = None,
                q_mask: torch.Tensor | None = None) -> torch.Tensor:
        f = self.image(image)
        n = f.size(0)
        if q_vec is None:  # questionnaire not given: every field missing (as in training)
            q_vec = f.new_zeros(n, self.n_q_features)
            q_mask = f.new_ones(n, self.n_q_fields)
        elif q_mask is None:
            raise ValueError("q_mask is required when q_vec is given")
        e = self.q_encoder(q_vec.to(f.dtype), q_mask.to(f.dtype))
        if self.fusion == "concat":
            h = torch.cat([f, e], dim=1)
        elif self.fusion == "gated":
            z = torch.sigmoid(self.gate(torch.cat([f, e], dim=1)))
            h = z * torch.tanh(self.proj_image(f)) + (1 - z) * torch.tanh(self.proj_q(e))
        else:
            gamma, beta = self.film(e).chunk(2, dim=1)
            h = f * (1 + gamma) + beta
        return self.classifier(self.head_dropout(h))

    @torch.no_grad()
    def gate_values(self, image, q_vec, q_mask) -> torch.Tensor:
        """Mean gate per sample (share taken from the photo); gated fusion only, for analysis."""
        if self.fusion != "gated":
            raise ValueError("gate_values needs fusion='gated'")
        f = self.image(image)
        e = self.q_encoder(q_vec.to(f.dtype), q_mask.to(f.dtype))
        return torch.sigmoid(self.gate(torch.cat([f, e], dim=1))).mean(1)
