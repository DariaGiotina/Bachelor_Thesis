import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import train  # noqa: E402

Q_COLS = ["f__a__x", "f__a__y", "f__b__rank"]
M_COLS = ["m__a", "m__b"]


def test_field_index_groups_columns_by_field():
    fields = train.field_index(Q_COLS, M_COLS)
    assert fields[0].tolist() == [0, 1] and fields[1].tolist() == [2]


def test_hide_answers_zeroes_features_and_sets_mask():
    fields = train.field_index(Q_COLS, M_COLS)
    q, m = torch.ones(8, 3), torch.zeros(8, 2)
    q2, m2 = train.hide_answers(q, m, fields, p_modality=1.0, p_field=0.0)
    assert q2.sum() == 0 and m2.sum() == 16          # everything hidden and flagged missing
    q3, m3 = train.hide_answers(q, m, fields, p_modality=0.0, p_field=0.0)
    assert torch.equal(q3, q) and torch.equal(m3, m)  # nothing hidden
    assert q.sum() == 24 and m.sum() == 0             # input tensors are not modified


def test_hidden_field_features_match_mask():
    fields = train.field_index(Q_COLS, M_COLS)
    q, m = torch.ones(200, 3), torch.zeros(200, 2)
    q2, m2 = train.hide_answers(q, m, fields, 0.0, 0.5, torch.Generator().manual_seed(0))
    assert ((q2[:, :2].sum(1) == 0) == (m2[:, 0] == 1)).all()
    assert ((q2[:, 2] == 0) == (m2[:, 1] == 1)).all()
