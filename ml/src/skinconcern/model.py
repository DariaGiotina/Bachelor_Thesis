"""Image backbone (transfer learning) + late fusion of questionnaire features.

The questionnaire branch receives the encoded answers ``q_vec`` together with the per-field
missingness mask ``q_mask`` (1 = not answered). A missing questionnaire is therefore represented
the same way at training and at inference: zero features and all mask entries set to 1. Answers
are hidden on purpose during training by the training script (modality dropout), not here.
"""
import timm
import torch
import torch.nn as nn


class FusionClassifier(nn.Module):
    def __init__(
        self,
        n_classes: int,
        n_q_features: int = 40,
        n_q_fields: int = 6,
        backbone: str = "efficientnet_b0",
        pretrained: bool = True,
        q_hidden: int = 64,
        use_questionnaire: bool = True,
    ):
        super().__init__()
        self.backbone = timm.create_model(backbone, pretrained=pretrained, num_classes=0)
        self.use_questionnaire = use_questionnaire
        self.n_q_features, self.n_q_fields = n_q_features, n_q_fields
        img_dim = self.backbone.num_features
        if use_questionnaire:
            self.q_net = nn.Sequential(nn.Linear(n_q_features + n_q_fields, q_hidden), nn.ReLU(), nn.Dropout(0.1))
            fused = img_dim + q_hidden
        else:
            fused = img_dim
        self.head = nn.Sequential(nn.Dropout(0.2), nn.Linear(fused, n_classes))

    def forward(self, image, q_vec=None, q_mask=None):
        f = self.backbone(image)
        if self.use_questionnaire:
            n = image.size(0)
            if q_vec is None:  # questionnaire not given at all: every field is missing
                q_vec = torch.zeros(n, self.n_q_features, device=image.device, dtype=f.dtype)
                q_mask = torch.ones(n, self.n_q_fields, device=image.device, dtype=f.dtype)
            elif q_mask is None:
                raise ValueError("q_mask is required when q_vec is given")
            q = torch.cat([q_vec, q_mask], dim=1).to(f.dtype)
            f = torch.cat([f, self.q_net(q)], dim=1)
        return self.head(f)
