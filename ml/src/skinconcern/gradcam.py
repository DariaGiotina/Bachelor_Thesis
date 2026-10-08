"""Grad-CAM heatmaps for the image branch."""
import numpy as np
import torch
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget


class _ImageOnly(torch.nn.Module):
    """Wrap the fusion model so Grad-CAM sees a single-input forward pass."""

    def __init__(self, model, q_vec=None, q_mask=None):
        super().__init__()
        self.model, self.q_vec, self.q_mask = model, q_vec, q_mask

    def forward(self, x):
        if self.q_vec is None:  # image-only model, or questionnaire treated as fully missing
            return self.model(x)
        n = x.size(0)
        return self.model(x, self.q_vec.expand(n, -1), self.q_mask.expand(n, -1))


def explain(model, image_tensor, rgb_image, target_class=None, q_vec=None, q_mask=None):
    """image_tensor: (1,3,H,W) normalized; rgb_image: float HxWx3 in [0,1]; q_vec/q_mask: (1,F)/(1,M)."""
    model.eval()
    wrapped = _ImageOnly(model, q_vec, q_mask)
    bb = model.backbone
    target_layer = [bb.conv_head if hasattr(bb, "conv_head") else list(bb.children())[-3]]
    cam = GradCAM(model=wrapped, target_layers=target_layer)
    targets = [ClassifierOutputTarget(target_class)] if target_class is not None else None
    heat = cam(input_tensor=image_tensor, targets=targets)[0]
    return show_cam_on_image(rgb_image.astype(np.float32), heat, use_rgb=True)
