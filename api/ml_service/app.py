"""ML inference service of the app (Task 5.1, first part): one photo in, one informational answer out.

The service loads the exported app model once (``ml/export/skin_concern_dinov2.onnx`` + its JSON,
written by ``ml/export_model.py``) and answers ``POST /v1/analyze`` with the decision of
``ml/serving.py``: ``answered`` (category and confidence), ``uncertain`` (see a professional) or
``unusual_photo`` (the photo is unlike the training photos). It is an internal service: the main
backend calls it after authenticating the user, so it holds no user data.

Privacy: the photo is decoded in memory, never written to disk and never logged; the response holds
no image data. Uploads are limited in size and pixel count; only JPEG, PNG and WebP are accepted.
No file is kept. If ``ML_SERVICE_KEY`` is set, every request must send it in
the ``X-Service-Key`` header (shared secret between the backend and this service).

Configuration (environment variables):
  SKINCONCERN_MODEL   path of the .onnx file (default: ml/export/skin_concern_dinov2.onnx)
  ML_SERVICE_KEY      shared secret; unset = no key required (local development only)
  MAX_UPLOAD_MB       largest accepted upload, default 10

Run::

    uvicorn api.ml_service.app:app --port 8001          # from the repository root
"""
from __future__ import annotations

import hmac
import io
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml"))
import serving  # noqa: E402

log = logging.getLogger("ml_service")
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 40_000_000  # about 7,000 x 6,000; larger files are refused (decompression bombs)
NOTICE = ("Informational result only, not a diagnosis. The app does not assess skin cancer or conditions "
          "outside its four categories; consult a professional for any new, changing, bleeding or painful lesion.")


def max_upload_bytes() -> int:
    return int(float(os.environ.get("MAX_UPLOAD_MB", "10")) * 2**20)


def load_model() -> serving.SkinConcernModel | None:
    path = Path(os.environ.get("SKINCONCERN_MODEL", serving.DEFAULT_MODEL))
    if not path.exists() or not path.with_suffix(".json").exists():
        log.error("model file %s (or its .json) not found; /v1/analyze answers 503", path)
        return None
    return serving.SkinConcernModel(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "model"):  # tests inject their own model
        app.state.model = load_model()
    yield


app = FastAPI(title="Skin-concern ML service", version="1.0.0", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)  # internal service: no public API docs


def require_key(x_service_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("ML_SERVICE_KEY")
    if expected and not (x_service_key and hmac.compare_digest(x_service_key, expected)):
        raise HTTPException(status_code=401, detail="missing or wrong service key")


def model_or_503() -> serving.SkinConcernModel:
    model = getattr(app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    return model


def read_photo(data: bytes) -> Image.Image:
    """Decode an uploaded photo in memory; upright (EXIF orientation applied), RGB."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ALLOWED_FORMATS:
                raise HTTPException(status_code=415, detail=f"unsupported image format {im.format}")
            if im.width * im.height > MAX_PIXELS:
                raise HTTPException(status_code=413, detail="image has too many pixels")
            im = ImageOps.exif_transpose(im)
            return im.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="the file is not a readable image") from None


@app.get("/health")
def health() -> dict:
    model = getattr(app.state, "model", None)
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    m = model.meta
    return {"status": "ok", "model": m["model"], "classes": m["classes"], "created": m["created"],
            "onnx_sha256": m["onnx_sha256"][:16]}


@app.post("/v1/analyze", dependencies=[Depends(require_key)])
def analyze(photo: UploadFile = File(...)) -> dict:
    model = model_or_503()
    data = photo.file.read(max_upload_bytes() + 1)
    if len(data) > max_upload_bytes():
        raise HTTPException(status_code=413, detail="file too large")
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    decision = model.analyze(read_photo(data))
    return {**decision.to_dict(), "notice": NOTICE, "model_sha256": model.meta["onnx_sha256"][:16]}
