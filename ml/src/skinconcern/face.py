"""MediaPipe Face Landmarker (Tasks API; successor of the legacy Face Mesh solution).

Download face_landmarker.task once and place it in ml/data/models/:
https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
"""
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "data" / "models" / "face_landmarker.task"


def face_landmarks(rgb: np.ndarray, model_path: Path = DEFAULT_MODEL):
    """Return (N,2) pixel landmarks (478 points) or None if no face is found."""
    opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(model_path)), num_faces=1
    )
    h, w = rgb.shape[:2]
    with vision.FaceLandmarker.create_from_options(opts) as lm:
        res = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.face_landmarks:
        return None
    return np.array([[p.x * w, p.y * h] for p in res.face_landmarks[0]])


def crop_face(rgb: np.ndarray, margin: float = 0.15, model_path: Path = DEFAULT_MODEL):
    pts = face_landmarks(rgb, model_path)
    if pts is None:
        return None
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    h, w = rgb.shape[:2]
    x0, y0 = int(max(0, x0 - mx)), int(max(0, y0 - my))
    x1, y1 = int(min(w, x1 + mx)), int(min(h, y1 + my))
    return rgb[y0:y1, x0:x1]
