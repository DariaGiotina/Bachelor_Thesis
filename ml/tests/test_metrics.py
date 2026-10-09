import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import evaluate  # noqa: E402
from skinconcern import metrics as M  # noqa: E402

CLASSES = ["acne", "eczema_dermatitis", "normal_other", "redness_rosacea"]


def _preds(n=300, seed=0, rows_per_case=1):
    rng = np.random.default_rng(seed)
    t = rng.choice(CLASSES, n, p=[0.1, 0.55, 0.3, 0.05])
    flip = rng.random(n) < 0.35
    p = np.where(flip, rng.choice(CLASSES, n), t)
    conf = np.clip(np.where(p == t, rng.uniform(0.5, 1.0, n), rng.uniform(0.25, 0.8, n)), 0, 1)
    df = pd.DataFrame({"case_id": [f"c{i // rows_per_case}" for i in range(n)], "split": "test",
                       "true_label": t, "pred_label": p, "confidence": conf,
                       "eFST": rng.choice([1, 2, 3, 4, 5, 6, np.nan], n), "eMST": rng.choice([1, 3, 5, 8, np.nan], n),
                       "seed": 0, "missing_pct": 0.0})
    return df


def test_macro_f1_and_balanced_accuracy_match_sklearn():
    d = _preds()
    assert M.macro_f1(d.true_label, d.pred_label) == pytest.approx(
        f1_score(d.true_label, d.pred_label, labels=np.unique(d.true_label), average="macro"))
    assert M.balanced_accuracy(d.true_label, d.pred_label) == pytest.approx(
        balanced_accuracy_score(d.true_label, d.pred_label))


def test_fast_bootstrap_metrics_equal_sklearn_definitions():
    d = _preds(seed=3)
    code = {c: i for i, c in enumerate(CLASSES)}
    f1, bal, acc, ece = M._fast_metrics(d.true_label.map(code).to_numpy(), d.pred_label.map(code).to_numpy(),
                                        d.confidence.to_numpy(), len(CLASSES), 15)
    fm = M.frame_metrics(15)
    assert f1 == pytest.approx(fm["macro_f1"](d))
    assert bal == pytest.approx(fm["balanced_acc"](d))
    assert acc == pytest.approx(fm["accuracy"](d))
    assert ece == pytest.approx(fm["ece"](d))


def test_ece_known_values():
    # perfectly calibrated: confidence 0.8, 80% correct
    assert M.expected_calibration_error([0.8] * 10, [1] * 8 + [0] * 2, n_bins=10) == pytest.approx(0.0)
    # always 0.9 confident, always wrong
    assert M.expected_calibration_error([0.9] * 5, [0] * 5, n_bins=10) == pytest.approx(0.9)


def test_per_class_report_handles_missing_class():
    rep = M.per_class_report(["acne", "acne"], ["acne", "eczema_dermatitis"], CLASSES)
    assert list(rep["class"]) == CLASSES
    assert rep.set_index("class").loc["redness_rosacea", "f1"] == 0.0


def test_risk_coverage_is_monotone_for_informative_confidence():
    conf = np.linspace(1, 0.3, 100)
    correct = np.r_[np.ones(60), np.zeros(40)]  # confident predictions are the correct ones
    rc = M.risk_coverage(conf, correct, coverages=[0.2, 0.6, 1.0])
    assert list(rc.accuracy) == [1.0, 1.0, 0.6]
    assert M.aurc(conf, correct) < M.aurc(conf[::-1], correct)


def test_bootstrap_resamples_cases_not_rows():
    """With 2 rows per case, a case-level bootstrap must keep both rows of a drawn case together."""
    d = _preds(n=200, rows_per_case=2)
    seen = []

    def metric(sample):
        seen.append(sample.groupby("case_id").size().unique().tolist())
        return M.macro_f1(sample.true_label, sample.pred_label)

    point, lo, hi = M.bootstrap_ci(d, metric, n_boot=30)
    assert all(all(k % 2 == 0 for k in s) for s in seen[1:])  # each drawn case keeps both of its rows
    assert lo <= point <= hi
    fast = M.bootstrap_standard_metrics(d, n_boot=200)
    assert fast["macro_f1"]["ci_low"] <= fast["macro_f1"]["value"] <= fast["macro_f1"]["ci_high"]


def test_tone_groups():
    assert [M.efst_group(v) for v in (1, 4, 6, None, -1)] == ["I-II", "III-IV", "V-VI", "missing", "missing"]
    assert [M.emst_group(v) for v in (2, 6, 7, 10, np.nan)] == ["1-3", "4-6", "7-10", "7-10", "missing"]


def test_evaluate_end_to_end(tmp_path):
    d = pd.concat([_preds(seed=s).assign(seed=s) for s in (0, 1)] +
                  [_preds(seed=0).assign(missing_pct=0.5)], ignore_index=True)
    path = tmp_path / "predictions_exp1.csv"
    d.to_csv(path, index=False)
    assert evaluate.main([str(path), "--n-boot", "100", "--min-group-n", "20"]) == 0
    import json
    s = json.loads((tmp_path / "metrics_summary.json").read_text())
    assert set(s["slices"]) == {"test|0|0.0", "test|1|0.0", "test|0|0.5"}
    sl = s["slices"]["test|0|0.0"]
    assert sl["eFST"]["worst_group"]["group"] in {"I-II", "III-IV", "V-VI"}
    assert {"value", "ci_low", "ci_high"} <= set(sl["overall"]["ece"])
    flat = pd.read_csv(tmp_path / "metrics_summary.csv")
    assert {"worst_group_macro_f1", "gap_macro_f1", "ece", "precision", "aurc"} <= set(flat.metric)
    assert (tmp_path / "risk_coverage.csv").exists()


def test_evaluate_rejects_duplicate_rows(tmp_path):
    d = _preds(n=20)
    path = tmp_path / "p.csv"
    pd.concat([d, d.iloc[:1]]).to_csv(path, index=False)
    with pytest.raises(ValueError):
        evaluate.main([str(path), "--n-boot", "10"])


def test_across_seeds_keeps_tone_groups_and_drops_worst_and_gap_rows():
    rows = []
    for seed, v in (("0", 0.4), ("1", 0.6)):
        base = {"split": "test", "seed": seed, "missing_pct": 0.0, "n_cases": 50, "ci_low": 0, "ci_high": 1}
        rows += [{**base, "scope": "eFST", "group": "I-II", "metric": "macro_f1", "value": v},
                 {**base, "scope": "eMST", "group": "1-3", "metric": "macro_f1", "value": v},
                 {**base, "scope": "eFST", "group": "worst=V-VI", "metric": "worst_group_macro_f1", "value": v},
                 {**base, "scope": "eFST", "group": "I-II-V-VI", "metric": "gap_macro_f1", "value": v}]
    agg = evaluate.across_seeds(pd.DataFrame(rows))
    assert set(agg["group"]) == {"I-II", "1-3"}
    assert (agg["n_seeds"] == 2).all() and np.allclose(agg["mean"], 0.5)
