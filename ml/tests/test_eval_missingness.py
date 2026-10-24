import numpy as np
import pandas as pd
import torch

import eval_missingness as em


def test_hide_zeroes_features_sets_mask_and_keeps_input():
    fields = [torch.tensor([0, 1]), torch.tensor([2])]
    q_vec = torch.ones(3, 3)
    q_mask = torch.zeros(3, 2)
    v, m = em.hide(q_vec, q_mask, fields, [0])
    assert torch.equal(v[:, :2], torch.zeros(3, 2)) and torch.equal(v[:, 2], torch.ones(3))
    assert torch.equal(m[:, 0], torch.ones(3)) and torch.equal(m[:, 1], torch.zeros(3))
    assert q_vec.sum() == 9 and q_mask.sum() == 0  # inputs untouched


def test_conditions_cover_hide_only_none_all():
    c = em.conditions(["a", "b", "c"])
    assert c["none"] == [] and c["all"] == [0, 1, 2]
    assert c["hide:b"] == [1] and c["only:b"] == [0, 2]
    assert len(c) == 2 + 2 * 3


def test_paired_difference_and_ci():
    a, b = np.array([0.5, 0.6, 0.7]), np.array([0.42, 0.48, 0.6])
    r = em.paired(a, b)
    assert np.isclose(r["delta"], 0.1) and r["n_neg"] == 0 and r["n"] == 3
    assert r["ci_low"] < r["delta"] < r["ci_high"]


def test_curve_repeats_photo_only_at_every_rate():
    rows = []
    for arm, rates in (("image_only", [0.0]), ("fusion_concat", [0.0, 0.5])):
        for r in rates:
            rows += [{"arm": arm, "seed": 0, "missing_pct": r, "true_label": t, "pred_label": t}
                     for t in ("x", "y")]
    out = em.curve(pd.DataFrame(rows), [0.0, 0.5])
    img = out[out["arm"] == "image_only"]
    assert sorted(img["condition"]) == ["r=0", "r=0.5"] and (img["macro_f1"] == 1.0).all()


def test_natural_groups_cover_all_cases():
    g = em.natural_groups()
    assert set(g.unique()) <= set(em.NATURAL_GROUPS)
    assert len(g) == 5033
