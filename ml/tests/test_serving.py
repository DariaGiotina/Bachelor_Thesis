import numpy as np
import pytest
from PIL import Image

import serving
from data_loading import build_transform


def _eval_path(img: Image.Image, size: int, cache_side: int = 448) -> np.ndarray:
    """What the evaluation saw: the cache copy (resize_image_cache.py), then build_transform without normalisation."""
    im = img.convert("RGB")
    scale = cache_side / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    cfg = {"data": {"image_size": size}, "normalize": {"mean": [0, 0, 0], "std": [1 / 255] * 3}}
    return build_transform(cfg, train=False)(image=np.asarray(im))["image"].numpy()


@pytest.mark.parametrize("wh", [(1000, 750), (640, 480), (300, 450), (448, 448), (517, 211)])
def test_preprocess_matches_evaluation_transform(wh):
    rng = np.random.default_rng(sum(wh))
    img = Image.fromarray(rng.integers(0, 256, (wh[1], wh[0], 3), dtype=np.uint8))
    ours = serving.preprocess(img, size=518)[0]
    ref = _eval_path(img, 518)
    assert ours.shape == ref.shape == (3, 518, 518)
    assert np.abs(ours - ref).max() <= 1.0  # same pixels up to rounding of one grey level


def test_decide_order_unusual_then_uncertain_then_answer():
    classes = ["acne", "eczema_dermatitis", "redness_rosacea", "normal_other"]
    p = np.array([0.1, 0.7, 0.1, 0.1])
    assert serving.decide(p, 0.9, classes, tau=0.5, knn_threshold=0.5).status == "unusual_photo"
    assert serving.decide(p, 0.1, classes, tau=0.8, knn_threshold=0.5).status == "uncertain"
    d = serving.decide(p, 0.1, classes, tau=0.5, knn_threshold=0.5)
    assert (d.status, d.category) == ("answered", "eczema_dermatitis")
    assert serving.decide(p, 0.1, classes, tau=0.8, knn_threshold=0.5).category is None
