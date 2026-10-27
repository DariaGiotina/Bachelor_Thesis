import numpy as np
import torch

import export_model as em
import ood_detect as ood


def _model(dim=8, n_classes=4, n_bank=30, t=1.5):
    torch.manual_seed(0)
    probe = {"state_dict": {"weight": torch.randn(n_classes, dim), "bias": torch.randn(n_classes)},
             "mean": torch.randn(dim), "std": torch.rand(dim) + 0.5}
    bank = torch.from_numpy(ood.l2n(np.random.default_rng(0).normal(size=(n_bank, dim)))).float()
    return em.AppModel(torch.nn.Identity(), probe, (0.5,) * 3, (0.25,) * 3, t, bank, k=5), probe, bank


def test_heads_match_probe_temperature_and_knn():
    model, probe, bank = _model()
    f = torch.randn(6, 8)
    prob, knn = model.heads(f)
    z = ((f - probe["mean"]) / probe["std"]) @ probe["state_dict"]["weight"].T + probe["state_dict"]["bias"]
    assert torch.allclose(prob, (z / 1.5).softmax(1), atol=1e-6)
    assert np.allclose(knn.numpy(), ood.knn_score(f.numpy(), bank.numpy(), k=5), atol=1e-5)


def test_pixel_normalisation_uses_0_255_range():
    model, _, _ = _model()
    x = torch.full((1, 3, 2, 2), 255 * 0.75)
    assert torch.allclose(model.features(x), torch.ones(1, 3, 2, 2))  # (0.75 - 0.5) / 0.25
