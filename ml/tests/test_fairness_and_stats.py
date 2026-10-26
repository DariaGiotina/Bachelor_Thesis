import numpy as np
import pandas as pd
import pytest

import analyze_fairness as af
import make_report_assets as mra
import stats_tests as st


def _frames(rng, seeds=(0, 1), n=120, noise=0.0):
    """One test split per seed with tones on both scales and predictions right except a share ``noise``."""
    out = {}
    for s in seeds:
        y = rng.integers(0, 4, n)
        p = np.where(rng.random(n) < noise, (y + 1) % 4, y)
        out[s] = pd.DataFrame({"case_id": [f"{s}-{i:04d}" for i in range(n)],
                               "true_label": np.array(af.CLASSES)[y], "pred_label": np.array(af.CLASSES)[p],
                               "confidence": 0.9, "eFST": rng.choice([1, 3, 5], n), "eMST": rng.choice([2, 5, 8], n)})
    return out


def test_perfect_model_scores_one_and_identical_arms_differ_by_zero():
    rng = np.random.default_rng(0)
    base = _frames(rng)
    frames = {"image_only": base, "copy": {s: d.copy() for s, d in base.items()}}
    point, boot, n = af.tone_scores(frames, [0, 1], n_boot=20)
    assert np.allclose(point[("image_only", "eFST", "I-II")][:, 0], 1.0)
    rows = pd.DataFrame(af.summarise("scin", point, boot, n, ["image_only", "copy"], [("delta", "copy", "image_only")]))
    d = rows[rows.kind == "delta"]
    assert np.allclose(d["mean"], 0) and np.allclose(d["ci_low"], 0) and np.allclose(d["ci_high"], 0)
    assert set(rows[rows.kind == "gap"]["scale"]) == {"eFST", "eMST"}


def test_different_test_cases_are_refused():
    rng = np.random.default_rng(1)
    a, b = _frames(rng), _frames(rng)
    b[0]["case_id"] = b[0]["case_id"] + "x"
    with pytest.raises(ValueError, match="test cases differ"):
        af.tone_scores({"image_only": a, "other": b}, [0, 1], n_boot=5)


def test_worse_model_has_negative_delta():
    rng = np.random.default_rng(2)
    good = _frames(rng, noise=0.1)
    bad = {s: d.assign(pred_label=np.where(np.arange(len(d)) % 2 == 0, "acne", d["pred_label"])) for s, d in good.items()}
    point, boot, n = af.tone_scores({"image_only": good, "bad": bad}, [0, 1], n_boot=50)
    rows = pd.DataFrame(af.summarise("scin", point, boot, n, ["image_only", "bad"], [("delta", "bad", "image_only")]))
    assert (rows[rows.kind == "delta"]["mean"] < 0).all()


def test_paired_contrast():
    a = pd.Series([0.6, 0.5, 0.7, 0.55], index=range(4))
    r = st.paired(a, a - 0.02 + np.array([0.0, 0.01, -0.01, 0.0]))
    assert r["mean"] == pytest.approx(0.02) and r["better_seeds"] == 4 and r["t_low"] < 0.02 < r["t_high"]
    with pytest.raises(ValueError):
        st.paired(a, a.set_axis(range(1, 5)))


def test_decimal_comma_only_inside_numbers():
    df = pd.DataFrame({"model": ["ViT-B/16 + probe. v1.0"], "macro_f1": ["0.519 ± 0.040"], "x": [0.5]})
    md = mra.to_markdown(df, decimal_comma=True)
    assert "0,519 ± 0,040" in md and "0,500" in md and "probe. v1,0" in md
