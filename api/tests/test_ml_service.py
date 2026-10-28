import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.ml_service import app as svc

serving = svc.serving

CLASSES = ["acne", "eczema_dermatitis", "redness_rosacea", "normal_other"]


class FakeModel:
    """Stands in for the ONNX model: records the photo size, answers with fixed probabilities."""
    meta = {"model": "fake", "classes": CLASSES, "created": "2026-10-27", "onnx_sha256": "0" * 64}

    def __init__(self, knn=0.1):
        self.knn, self.seen = knn, []

    def analyze(self, image):
        self.seen.append(image.size)
        return serving.decide(np.array([0.1, 0.7, 0.1, 0.1]), self.knn, CLASSES, tau=0.5, knn_threshold=0.45)


def _png(w=64, h=48, fmt="PNG", exif_rotate=False) -> bytes:
    im = Image.fromarray(np.random.default_rng(0).integers(0, 255, (h, w, 3), dtype=np.uint8))
    buf = io.BytesIO()
    if exif_rotate:
        exif = Image.Exif()
        exif[0x0112] = 6  # orientation: rotate 90 degrees
        im.save(buf, format="JPEG", exif=exif)
    else:
        im.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_KEY", raising=False)
    model = FakeModel()
    svc.app.state.model = model
    with TestClient(svc.app) as c:
        c.model = model
        yield c
    del svc.app.state.model


def test_analyze_returns_decision_and_notice(client):
    r = client.post("/v1/analyze", content=_png(), headers={"Content-Type": "image/png"})
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["category"]) == ("answered", "eczema_dermatitis")
    assert "not a diagnosis" in body["notice"]


def test_exif_orientation_is_applied(client):
    client.post("/v1/analyze", content=_png(64, 48, exif_rotate=True), headers={"Content-Type": "image/jpeg"})
    assert client.model.seen[-1] == (48, 64)  # upright: width and height swapped


@pytest.mark.parametrize("payload,code", [(b"", 400), (b"not an image", 400)])
def test_bad_uploads_are_refused(client, payload, code):
    assert client.post("/v1/analyze", content=payload, headers={"Content-Type": "image/png"}).status_code == code


def test_unsupported_format_and_size_limits(client, monkeypatch):
    assert client.post("/v1/analyze", content=_png(fmt="GIF"), headers={"Content-Type": "image/gif"}).status_code == 415
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.001")
    assert client.post("/v1/analyze", content=_png(200, 200), headers={"Content-Type": "image/png"}).status_code == 413


def test_service_key_is_required_when_set(client, monkeypatch):
    monkeypatch.setenv("ML_SERVICE_KEY", "secret")
    body = _png()
    assert client.post("/v1/analyze", content=body).status_code == 401
    assert client.post("/v1/analyze", content=body, headers={"X-Service-Key": "wrong"}).status_code == 401
    assert client.post("/v1/analyze", content=body, headers={"X-Service-Key": "secret"}).status_code == 200


def test_no_model_gives_503(monkeypatch):
    svc.app.state.model = None
    with TestClient(svc.app) as c:
        assert c.get("/health").status_code == 503
        assert c.post("/v1/analyze", content=_png(), headers={"Content-Type": "image/png"}).status_code == 503
    del svc.app.state.model


@pytest.mark.skipif(not serving.DEFAULT_MODEL.exists(), reason="exported model not on this machine")
def test_real_model_end_to_end(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_KEY", raising=False)
    svc.app.state.model = svc.load_model()
    with TestClient(svc.app) as c:
        assert c.get("/health").json()["classes"] == CLASSES
        body = c.post("/v1/analyze", content=_png(300, 200), headers={"Content-Type": "image/png"}).json()
    del svc.app.state.model
    assert body["status"] in {"answered", "uncertain", "unusual_photo"}
    assert abs(sum(body["probabilities"].values()) - 1) < 1e-3


def test_streamed_body_without_length_is_capped(client, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.01")
    chunks = (b"x" * 4096 for _ in range(10))  # 40 kB, sent chunked: no Content-Length header
    assert client.post("/v1/analyze", content=chunks).status_code == 413
    assert client.model.seen == []
