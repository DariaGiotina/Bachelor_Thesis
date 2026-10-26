import sys
from pathlib import Path

import numpy as np
import torch

import ood_detect as ood

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labels"))
import build_labels as bl  # noqa: E402


def _clusters(rng, n=300, d=16):
    centres = np.eye(d)[:3] * 6
    y = rng.integers(0, 3, n)
    return centres[y] + rng.normal(0, 1, (n, d)), y


def test_far_points_score_higher():
    rng = np.random.default_rng(0)
    x, y = _clusters(rng)
    near, _ = _clusters(rng, 50)
    far = rng.normal(0, 1, (50, 16)) + np.r_[np.zeros(8), np.full(8, 6.0)]
    maha = ood.fit_mahalanobis(x, y)
    assert ood.mahalanobis_score(far, maha).min() > np.median(ood.mahalanobis_score(near, maha))
    train = ood.l2n(x)
    assert ood.knn_score(far, train).mean() > ood.knn_score(near, train).mean()


def test_knn_score_is_zero_on_duplicates():
    x = ood.l2n(np.random.default_rng(1).normal(size=(20, 8)))
    assert np.allclose(ood.knn_score(x, np.repeat(x, 3, axis=0), k=3), 0, atol=1e-6)


def test_threshold_flags_five_percent_of_validation():
    v = np.random.default_rng(2).normal(size=10_000)
    assert abs((v > ood.threshold(v)).mean() - 0.05) < 0.002


def test_probe_probs_match_torch_linear():
    rng = np.random.default_rng(3)
    lin = torch.nn.Linear(6, 4)
    mean, std = torch.tensor(rng.normal(size=6), dtype=torch.float32), torch.rand(6) + 0.5
    x = rng.normal(size=(10, 6)).astype(np.float32)
    ref = lin((torch.from_numpy(x) - mean) / std).softmax(1).detach().numpy()
    probe = {"state_dict": lin.state_dict(), "mean": mean, "std": std}
    assert np.allclose(ood.probe_probs(x, probe), ref, atol=1e-5)


def test_in_scope_weight_ignores_unmapped_strings():
    cfg = {"unmapped_class": "excluded", "lookup": {"eczema": "eczema_dermatitis", "acne": "acne",
                                                    "melanoma": "excluded"}}
    assert bl.in_scope_weight({"Eczema": 0.5, "Tinea": 0.5}, cfg) == 0.5
    assert bl.in_scope_weight({"Tinea": 0.6, "Melanoma": 0.4}, cfg) == 0
    assert bl.in_scope_weight({}, cfg) == 0
