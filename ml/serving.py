"""Inference for the exported app model (Task 4.5): preprocessing, ONNX session and the decision rule.

The exported model (``export_model.py``) is the frozen DINOv2 ViT-B/14 encoder + the linear probe of
one split seed, with its calibration temperature T folded into the graph and the kNN bank of that
seed's SCIN training features. One ONNX file returns, per image, the calibrated class probabilities
and the kNN score (1 - cosine similarity to the 10th nearest training case). The JSON written beside
it holds the classes, tau, the kNN threshold and the preprocessing.

Decision rule (Task 4.2b), applied in this order:
  unusual_photo   kNN score above the threshold: the photo is unlike every training photo
  uncertain       calibrated confidence below tau: "uncertain, see a professional"
  answered        otherwise: the most likely category, shown with its confidence
The answer is informational only ("may indicate", never a diagnosis). The red-flag questions and the
permanent notice of what the app does not assess are part of the app, not of this module.

This module needs only numpy, Pillow, OpenCV and onnxruntime, so the FastAPI service can import it
without PyTorch. ``preprocess`` reproduces the evaluation transform of ``data_loading.py`` (cache
copy with longest side 448 px, then letterbox to the encoder size); ``tests/test_serving.py`` checks
that both give the same tensor.

Usage::

    python serving.py photo.jpg                       # uses export/skin_concern_dinov2.onnx
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / "export" / "skin_concern_dinov2.onnx"


# ------------------------------------------------------------------------------- preprocessing
def preprocess(image: Image.Image | np.ndarray, size: int = 518, cache_side: int = 448) -> np.ndarray:
    """RGB photo -> float32 (1, 3, size, size) with pixel values 0-255; the graph normalises.

    Same steps as the evaluation path: (1) longest side down to ``cache_side`` with Lanczos if larger
    (``scripts/resize_image_cache.py``), (2) longest side to ``size`` with bilinear interpolation and
    (3) black padding to a centred square (albumentations ``LongestMaxSize`` + ``PadIfNeeded``).
    """
    im = image if isinstance(image, Image.Image) else Image.fromarray(np.asarray(image, np.uint8))
    im = im.convert("RGB")
    scale = cache_side / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    a = np.asarray(im)
    h, w = a.shape[:2]
    s = size / max(h, w)
    nh, nw = max(1, round(h * s)), max(1, round(w * s))
    if (nh, nw) != (h, w):
        a = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_LINEAR)
    top, left = (size - nh) // 2, (size - nw) // 2
    out = np.zeros((size, size, 3), np.uint8)
    out[top:top + nh, left:left + nw] = a
    return np.ascontiguousarray(out.transpose(2, 0, 1)[None], dtype=np.float32)


# ----------------------------------------------------------------------------------- decision
@dataclass(frozen=True)
class Decision:
    status: str                     # answered | uncertain | unusual_photo
    category: str | None            # shown only when status == "answered"
    confidence: float               # calibrated largest class probability
    probabilities: dict[str, float]
    knn_score: float

    def to_dict(self) -> dict:
        return {"status": self.status, "category": self.category, "confidence": round(self.confidence, 4),
                "probabilities": {k: round(v, 4) for k, v in self.probabilities.items()},
                "knn_score": round(self.knn_score, 4)}


def decide(prob: np.ndarray, knn: float, classes: list[str], tau: float, knn_threshold: float) -> Decision:
    prob = np.asarray(prob, float)
    j = int(prob.argmax())
    probs = dict(zip(classes, map(float, prob)))
    if knn > knn_threshold:
        return Decision("unusual_photo", None, float(prob[j]), probs, float(knn))
    if prob[j] < tau:
        return Decision("uncertain", None, float(prob[j]), probs, float(knn))
    return Decision("answered", classes[j], float(prob[j]), probs, float(knn))


# -------------------------------------------------------------------------------------- model
class SkinConcernModel:
    """ONNX model + its JSON metadata. ``analyze(photo)`` returns a ``Decision``."""

    def __init__(self, onnx_path: Path = DEFAULT_MODEL, providers: list[str] | None = None):
        import onnxruntime as ort

        onnx_path = Path(onnx_path)
        self.meta = json.loads(onnx_path.with_suffix(".json").read_text(encoding="utf-8"))
        self.session = ort.InferenceSession(str(onnx_path), providers=providers or ["CPUExecutionProvider"])
        self.classes = self.meta["classes"]
        self.size = self.meta["preprocessing"]["input_size"]
        self.cache_side = self.meta["preprocessing"]["cache_longest_side"]

    def run(self, batch: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        prob, knn = self.session.run(["probabilities", "knn_score"], {"image": batch.astype(np.float32)})
        return prob, knn

    def analyze(self, image: Image.Image | np.ndarray) -> Decision:
        prob, knn = self.run(preprocess(image, self.size, self.cache_side))
        return decide(prob[0], float(knn[0]), self.classes, self.meta["tau"], self.meta["knn"]["threshold"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("images", type=Path, nargs="+")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = ap.parse_args(argv)
    model = SkinConcernModel(args.model)
    for p in args.images:
        with Image.open(p) as im:
            print(p.name, json.dumps(model.analyze(im).to_dict()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
