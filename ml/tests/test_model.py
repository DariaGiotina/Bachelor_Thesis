import torch

from skinconcern.metrics import stratified_report
from skinconcern.model import FusionClassifier


def _model(**kw):
    return FusionClassifier(n_classes=5, n_questionnaire=8, pretrained=False, **kw)


def test_forward_with_and_without_questionnaire():
    m = _model().eval()
    x = torch.randn(2, 3, 224, 224)
    assert m(x, torch.randn(2, 8)).shape == (2, 5)
    assert m(x).shape == (2, 5)  # fully missing answers


def test_image_only_baseline():
    m = _model(use_questionnaire=False).eval()
    assert m(torch.randn(2, 3, 224, 224)).shape == (2, 5)


def test_stratified_report():
    r = stratified_report([0, 1, 0, 1], [0, 1, 1, 1], ["I", "I", "VI", "VI"])
    assert set(r.group) == {"ALL", "I", "VI"}
