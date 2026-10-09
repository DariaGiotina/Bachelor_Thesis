import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import run_q_only as rq  # noqa: E402
import train  # noqa: E402
from models.q_model import QuestionnaireMLP  # noqa: E402

Q_COLS = ["f__a__x", "f__a__y", "f__b__rank"]
M_COLS = ["m__a", "m__b"]


def test_mlp_shapes_and_input_check():
    m = QuestionnaireMLP(3, 2, 4, hidden=8, depth=2)
    assert m(torch.zeros(5, 3), torch.ones(5, 2)).shape == (5, 4)
    with pytest.raises(ValueError):
        m(torch.zeros(5, 4), torch.ones(5, 2))


def test_mask_changes_the_output():
    torch.manual_seed(0)
    m = QuestionnaireMLP(3, 2, 4, hidden=8).eval()
    q = torch.zeros(1, 3)
    assert not torch.allclose(m(q, torch.zeros(1, 2)), m(q, torch.ones(1, 2)))  # "not answered" is visible


def test_eval_hiding_matches_the_fusion_evaluation():
    fields = train.field_index(Q_COLS, M_COLS)
    batches = [{"image": torch.zeros(4, 1), "q_vec": torch.ones(4, 3), "q_mask": torch.zeros(4, 2)} for _ in range(3)]
    fus = train.make_fusion_adapt(fields, 0.0, 0.0, p_field_eval=0.5, seed=7)
    q = rq.make_q_adapt(fields, 0.0, p_field_eval=0.5, seed=7)
    for b in batches:
        a, c = fus(b, False), q(b, False)
        assert torch.equal(a["q_mask"], c["q_mask"]) and torch.equal(a["q_vec"], c["q_vec"])


def test_no_hiding_when_rate_is_zero():
    fields = train.field_index(Q_COLS, M_COLS)
    b = {"q_vec": torch.ones(4, 3), "q_mask": torch.zeros(4, 2)}
    out = rq.make_q_adapt(fields, 0.0, 0.0, seed=0)(b, False)
    assert torch.equal(out["q_vec"], b["q_vec"]) and torch.equal(out["q_mask"], b["q_mask"])
