"""Image backbone (transfer learning) + late fusion of questionnaire features."""
import timm
import torch
import torch.nn as nn


class ModalityDropout(nn.Module):
    """During training, zero the whole questionnaire vector with probability p.

    A binary availability flag is returned so the model can tell "missing"
    apart from "answered with zeros".
    """

    def __init__(self, p: float = 0.3):
        super().__init__()
        self.p = p

    def forward(self, q: torch.Tensor, available: torch.Tensor | None = None):
        if available is None:
            available = torch.ones(q.size(0), device=q.device)
        if self.training and self.p > 0:
            keep = (torch.rand(q.size(0), device=q.device) >= self.p).float()
            available = available * keep
        return q * available.unsqueeze(1), available


class FusionClassifier(nn.Module):
    def __init__(
        self,
        n_classes: int,
        n_questionnaire: int,
        backbone: str = "efficientnet_b0",
        pretrained: bool = True,
        q_hidden: int = 64,
        p_dropout: float = 0.3,
        use_questionnaire: bool = True,
    ):
        super().__init__()
        self.backbone = timm.create_model(backbone, pretrained=pretrained, num_classes=0)
        self.use_questionnaire = use_questionnaire
        img_dim = self.backbone.num_features
        if use_questionnaire:
            self.mod_dropout = ModalityDropout(p_dropout)
            self.q_net = nn.Sequential(nn.Linear(n_questionnaire, q_hidden), nn.ReLU(), nn.Dropout(0.1))
            fused = img_dim + q_hidden + 1  # +1: availability flag
        else:
            fused = img_dim
        self.head = nn.Sequential(nn.Dropout(0.2), nn.Linear(fused, n_classes))

    def forward(self, image, questionnaire=None, available=None):
        f = self.backbone(image)
        if self.use_questionnaire:
            if questionnaire is None:  # fully missing at inference
                questionnaire = torch.zeros(image.size(0), self.q_net[0].in_features, device=image.device)
                available = torch.zeros(image.size(0), device=image.device)
            q, a = self.mod_dropout(questionnaire, available)
            f = torch.cat([f, self.q_net(q), a.unsqueeze(1)], dim=1)
        return self.head(f)
