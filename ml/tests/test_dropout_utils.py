import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import dropout_utils as du  # noqa: E402
import train  # noqa: E402

Q_COLS = ["f__a__x", "f__a__y", "f__b__rank", "f__c__z"]
M_COLS = ["m__a", "m__b", "m__c"]
FIELDS = du.field_index(Q_COLS, M_COLS)


def batch(n=64):
    return {"image": torch.zeros(n, 3, 4, 4), "q_vec": torch.ones(n, 4), "q_mask": torch.zeros(n, 3)}


def test_full_dropout_hides_everything_and_keeps_inputs():
    q, m = torch.ones(8, 4), torch.zeros(8, 3)
    q2, m2 = du.apply_answer_dropout(q, m, p_field=0.0, p_full=1.0, fields=FIELDS)
    assert q2.sum() == 0 and m2.sum() == 24
    assert q.sum() == 32 and m.sum() == 0  # inputs untouched


def test_dropped_fields_are_zeroed_exactly_where_mask_is_set():
    q2, m2 = du.apply_answer_dropout(torch.ones(500, 4), torch.zeros(500, 3), 0.5, 0.0, FIELDS,
                                     torch.Generator().manual_seed(0))
    for j, cols in enumerate(FIELDS):
        assert ((q2[:, cols].sum(1) == 0) == (m2[:, j] == 1)).all()
    assert 0.4 < m2.mean() < 0.6


def test_already_missing_fields_stay_missing():
    m = torch.zeros(10, 3)
    m[:, 1] = 1.0
    _, m2 = du.apply_answer_dropout(torch.ones(10, 4), m, 0.0, 0.0, FIELDS)
    assert (m2[:, 1] == 1).all() and m2[:, [0, 2]].sum() == 0


def test_hide_answers_wrapper_matches_new_function():
    """train.hide_answers (used by run_q_only) must draw the same hidden answers as before."""
    a = train.hide_answers(torch.ones(50, 4), torch.zeros(50, 3), FIELDS, 0.2, 0.3, torch.Generator().manual_seed(3))
    b = du.apply_answer_dropout(torch.ones(50, 4), torch.zeros(50, 3), 0.3, 0.2, FIELDS,
                                torch.Generator().manual_seed(3))
    assert torch.equal(a[0], b[0]) and torch.equal(a[1], b[1])


def test_sample_p_field_range_and_validation():
    g = torch.Generator().manual_seed(0)
    ps = [du.sample_p_field(0.2, 0.6, g) for _ in range(200)]
    assert min(ps) >= 0.2 and max(ps) <= 0.6 and max(ps) - min(ps) > 0.3
    with pytest.raises(ValueError):
        du.sample_p_field(0.7, 0.2)


def test_training_rates_modes():
    cfg = {"train": {"p_modality_drop": 0.3, "p_field_drop": 0.15},
           "answer_dropout": {"p_full": 0.05, "p_field_low": 0.0, "p_field_high": 1.0}}
    assert du.training_rates("none", cfg) == {"mode": "none", "p_full": 0.0, "p_field": 0.0}
    assert du.training_rates("fixed", cfg)["p_field"] == 0.15
    assert du.training_rates("random", cfg)["p_full"] == 0.05
    with pytest.raises(ValueError):
        du.training_rates("sometimes", cfg)


def test_random_mode_varies_rate_between_batches_and_not_in_eval():
    rates = {"mode": "random", "p_full": 0.0, "p_field_low": 0.0, "p_field_high": 1.0}
    adapt = du.make_dropout_adapt(FIELDS, rates, seed=0)
    shares = [adapt(batch(400), training=True)["q_mask"].mean().item() for _ in range(20)]
    assert max(shares) - min(shares) > 0.3          # a different rate per batch
    out = adapt(batch(), training=False)            # evaluation with p_field_eval = 0: nothing hidden
    assert out["q_mask"].sum() == 0 and out["q_vec"].sum() == 64 * 4


def test_none_mode_never_hides_answers():
    adapt = du.make_dropout_adapt(FIELDS, du.training_rates("none", {"train": {}}), seed=0)
    assert adapt(batch(), training=True)["q_mask"].sum() == 0


def test_fixed_mode_matches_old_make_fusion_adapt():
    old = train.make_fusion_adapt(FIELDS, 0.3, 0.15, seed=4)
    new = du.make_dropout_adapt(FIELDS, {"mode": "fixed", "p_full": 0.3, "p_field": 0.15}, seed=4)
    for _ in range(3):
        assert torch.equal(old(batch(), True)["q_mask"], new(batch(), True)["q_mask"])
