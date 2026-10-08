import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import engine  # noqa: E402
import losses  # noqa: E402


def _batches(n=4, bs=8, classes=3):
    g = torch.Generator().manual_seed(0)
    return [{"image": torch.randn(bs, 3, 8, 8, generator=g), "label": torch.randint(0, classes, (bs,), generator=g),
             "eFST": torch.randint(1, 7, (bs,), generator=g), "case_id": torch.arange(bs)} for _ in range(n)]


class Tiny(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(3 * 8 * 8, 3)

    def forward(self, image):
        return self.fc(image.flatten(1))


def test_train_and_evaluate_return_metrics():
    model, device = Tiny(), torch.device("cpu")
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.SGD(model.parameters(), lr=0.1)
    scaler = torch.amp.GradScaler(enabled=False)
    data = _batches()
    first = engine.evaluate(model, data, loss_fn, device)["loss"]
    for _ in range(30):
        engine.train_one_epoch(model, data, loss_fn, opt, scaler, device)
    res = engine.evaluate(model, data, loss_fn, device)
    assert res["loss"] < first
    assert 0.0 <= res["macro_f1"] <= 1.0 and res["n"] == 32 and len(res["y_pred"]) == 32


def test_early_stopping_tracks_best_and_stops():
    es = engine.EarlyStopping(patience=2)
    assert es.step(0.5, 0) and es.step(0.6, 1)
    assert not es.step(0.55, 2) and not es.should_stop
    assert not es.step(0.58, 3) and es.should_stop
    assert es.best == 0.6 and es.best_epoch == 1


def test_focal_with_gamma_zero_equals_weighted_cross_entropy():
    logits, y = torch.randn(16, 4), torch.randint(0, 4, (16,))
    w = torch.tensor([1.0, 2.0, 0.5, 1.5])
    assert torch.allclose(losses.FocalLoss(0.0, w)(logits, y), nn.CrossEntropyLoss(weight=w)(logits, y), atol=1e-6)
    assert torch.allclose(losses.FocalLoss(0.0)(logits, y), nn.CrossEntropyLoss()(logits, y), atol=1e-6)
    assert losses.FocalLoss(2.0)(logits, y) < losses.FocalLoss(0.0)(logits, y)


def test_class_weights_favour_rare_classes():
    w = losses.class_weights(np.array([0] * 90 + [1] * 10), 2)
    assert w[1] > w[0]
    assert losses.build_loss("focal", np.array([0, 1]), 2, torch.device("cpu")).gamma == 2.0
