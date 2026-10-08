import numpy as np
import pytest
import torch

from skinconcern.metrics import bootstrap_ci, macro_f1, max_gap, stratified_report
from skinconcern.model import FusionClassifier


def _model(**kw):
    return FusionClassifier(n_classes=4, n_q_features=8, n_q_fields=3, pretrained=False, **kw)


def test_forward_with_and_without_questionnaire():
    m = _model().eval()
    x = torch.randn(2, 3, 224, 224)
    assert m(x, torch.randn(2, 8), torch.zeros(2, 3)).shape == (2, 4)
    assert m(x).shape == (2, 4)  # questionnaire not given


def test_missing_questionnaire_equals_all_fields_masked():
    """No questionnaire must be the same input as zero features with every mask entry = 1."""
    m = _model().eval()
    x = torch.randn(2, 3, 224, 224)
    with torch.no_grad():
        assert torch.allclose(m(x), m(x, torch.zeros(2, 8), torch.ones(2, 3)))


def test_q_mask_required_with_q_vec():
    with pytest.raises(ValueError):
        _model().eval()(torch.randn(1, 3, 224, 224), torch.randn(1, 8))


def test_image_only_baseline():
    m = _model(use_questionnaire=False).eval()
    assert m(torch.randn(2, 3, 224, 224)).shape == (2, 4)


def test_stratified_report_and_gap_ignore_missing_group():
    y = [0, 1, 0, 1, 0, 1]
    p = [0, 1, 1, 1, 0, 0]
    r = stratified_report(y, p, ["I-II", "I-II", "V-VI", "V-VI", "missing", "missing"], n_boot=50)
    assert set(r.group) == {"ALL", "I-II", "V-VI", "missing"}
    assert {"ci_low", "ci_high"} <= set(r.columns)
    gap = max_gap(r)
    tone = r[r.group.isin(["I-II", "V-VI"])].macro_f1
    assert gap == pytest.approx(tone.max() - tone.min())


def test_macro_f1_uses_classes_present_in_group():
    # class 2 absent from y_true; one false prediction of it should not add an extra 0 to the mean
    y, p = np.array([0, 0, 1, 1]), np.array([0, 2, 1, 1])
    assert macro_f1(y, p) == pytest.approx((2 / 3 + 1.0) / 2)


def test_bootstrap_ci_contains_point_estimate():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 200)
    p = np.where(rng.random(200) < 0.7, y, rng.integers(0, 3, 200))
    lo, hi = bootstrap_ci(y, p, n_boot=200, seed=0)
    assert lo <= macro_f1(y, p) <= hi
