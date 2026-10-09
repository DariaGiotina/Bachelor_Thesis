import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import run_e1  # noqa: E402

CLASSES = ["a", "b", "c"]


def _preds(arm, seed, pred_fn, n=60, rates=(0.0,)):
    rng = np.random.default_rng(seed)
    true = rng.choice(CLASSES, n)
    rows = []
    for r in rates:
        pred = pred_fn(true, rng, r)
        rows.append(pd.DataFrame({"case_id": [f"{seed}_{i:03d}" for i in range(n)], "split": "test", "true_label": true,
                                  "pred_label": pred, "confidence": 0.7, "seed": seed, "missing_pct": r, "arm": arm}))
    return pd.concat(rows)


def perfect(true, rng, r):
    return true


def noisy(true, rng, r):
    return np.where(rng.uniform(size=len(true)) < 0.4, rng.choice(CLASSES, len(true)), true)


def test_identical_arms_have_zero_paired_difference():
    preds = pd.concat([_preds(a, s, perfect) for a in ("image_only", "fusion_concat") for s in (0, 1, 2)])
    arms, pairs = run_e1.summarise(preds, ["image_only", "fusion_concat"], [0, 1, 2], CLASSES, 200, 15, 0)
    p = pairs.iloc[0]
    assert p["mean"] == 0 and p["ci_low"] == 0 and p["ci_high"] == 0 and np.isnan(p["wilcoxon_p"])
    f1 = arms[(arms.arm == "image_only") & (arms.metric == "macro_f1")].iloc[0]
    assert f1["mean"] == 1.0 and f1["ci_low"] == 1.0


def test_better_arm_wins_every_seed_and_ci_excludes_zero():
    preds = pd.concat([_preds("fusion_concat", s, perfect) for s in (0, 1, 2)]
                      + [_preds("image_only", s, noisy) for s in (0, 1, 2)])
    _, pairs = run_e1.summarise(preds, ["image_only", "fusion_concat"], [0, 1, 2], CLASSES, 300, 15, 0)
    p = pairs.iloc[0]
    assert (p["arm"], p["versus"]) == ("fusion_concat", "image_only")
    assert p["a_better_seeds"] == 3 and p["ci_low"] > 0
    assert all(p[f"seed{s}"] > 0 for s in (0, 1, 2))


def test_all_hidden_row_only_for_questionnaire_arms():
    preds = pd.concat([_preds("image_only", s, perfect) for s in (0, 1)]
                      + [_preds("fusion_concat", s, perfect, rates=(0.0, 1.0)) for s in (0, 1)])
    arms, _ = run_e1.summarise(preds, ["image_only", "fusion_concat"], [0, 1], CLASSES, 50, 15, 0)
    hidden = arms[arms.missing_pct == 1.0]
    assert hidden["arm"].tolist() == ["fusion_concat"]


def test_different_test_cases_are_rejected():
    a = _preds("image_only", 0, perfect)
    b = _preds("fusion_concat", 0, perfect)
    b["case_id"] = b["case_id"].str.replace("0_000", "9_999")
    with pytest.raises(ValueError, match="different cases"):
        run_e1.summarise(pd.concat([a, b]), ["image_only", "fusion_concat"], [0], CLASSES, 20, 15, 0)


def test_pairs_cover_the_comparisons():
    p = run_e1.pairs(["image_only", "questionnaire_only", "fusion_concat", "fusion_gated"])
    assert ("fusion_gated", "image_only") in p and ("fusion_gated", "fusion_concat") in p
    assert ("image_only", "questionnaire_only") in p and ("fusion_concat", "fusion_concat") not in p


def test_arm_spec_names_runs():
    s = run_e1.arm_spec("fusion_concat_nodrop", "efficientnet_b0", "weighted_loss")
    assert s["dir"].name == "efficientnet_b0_concat_weighted_loss_nodrop" and s["questionnaire"]
    with pytest.raises(ValueError):
        run_e1.arm_spec("fusion_attention", "efficientnet_b0", "weighted_loss")
