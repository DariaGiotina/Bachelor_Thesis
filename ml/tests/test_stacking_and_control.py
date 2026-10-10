import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "analysis"))
import fusion_positive_control as pc  # noqa: E402
import run_stacking as rs  # noqa: E402
import train  # noqa: E402

Q_COLS = ["f__a__x", "f__a__y", "f__b__rank"]
M_COLS = ["m__a", "m__b"]


def test_hidden_q_matches_fusion_evaluation_draws():
    """Stacking must hide the same answers as run_fusion / run_q_only (same generator use per batch)."""
    fields = train.field_index(Q_COLS, M_COLS)
    ds = SimpleNamespace(q_vec=np.ones((70, 3), np.float32), q_mask=np.zeros((70, 2), np.float32))
    q, m = rs.hidden_q(ds, fields, 0.5, seed=3, batch_size=32)
    adapt = train.make_fusion_adapt(fields, 0.0, 0.0, p_field_eval=0.5, seed=3)
    ref = [adapt({"image": None, "q_vec": torch.ones(n, 3), "q_mask": torch.zeros(n, 2)}, False)["q_mask"]
           for n in (32, 32, 6)]
    assert np.array_equal(m, torch.cat(ref).numpy())
    q0, m0 = rs.hidden_q(ds, fields, 0.0, 3, 32)
    assert q0.sum() == 210 and m0.sum() == 0


def test_features_per_arm():
    lp, q, m = np.zeros((5, 4)), np.ones((5, 3)), np.ones((5, 2))
    assert rs.features("stack_photo", lp, q, m).shape == (5, 4)
    assert rs.features("stack_photo_q", lp, q, m).shape == (5, 9)
    assert rs.features("stack_q", lp, q, m).shape == (5, 5)


def test_subset_keeps_labels_and_epoch():
    calls = []
    ds = SimpleNamespace(labels=np.array([0, 1, 2, 3]), classes=["a", "b", "c", "d"],
                         set_epoch=calls.append, __getitem__=None)
    sub = rs.Subset(ds, [1, 3])
    assert sub.labels.tolist() == [1, 3] and len(sub) == 2
    sub.set_epoch(4)
    assert calls == [4]


def test_fit_combiner_uses_an_informative_feature():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 300)
    x = np.c_[np.eye(3)[y] + rng.normal(0, 0.3, (300, 3)), rng.normal(size=(300, 2))]
    _, (f1, c, clf) = rs.fit_combiner(x[:200], y[:200], x[200:], y[200:], 0)
    assert f1 > 0.9 and c in rs.C_GRID


def test_synthetic_answer_is_fixed_per_case_and_matches_agreement():
    ids, y = torch.arange(4000), torch.randint(0, 4, (4000,), generator=torch.Generator().manual_seed(0))
    a1 = pc.synthetic_answer(ids, y, 0.5, 4, seed=1)
    a2 = pc.synthetic_answer(ids, y, 0.5, 4, seed=1)
    assert torch.equal(a1, a2)                                  # same answer every epoch
    agree = (a1 == y).float().mean().item()
    assert 0.58 < agree < 0.67                                  # 0.5 + 0.5 * 1/4 = 0.625
    assert (pc.synthetic_answer(ids, y, 1.0, 4, 1) == y).all()
