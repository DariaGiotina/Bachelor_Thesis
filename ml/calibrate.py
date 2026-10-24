"""E4 / Task 4.2: temperature scaling, and full class probabilities for every E4 arm.

Temperature scaling divides the logits by one number T > 0 before the softmax. T is fitted on the
validation split by minimising the negative log-likelihood (NLL); it never changes which class is
predicted (the order of the logits is kept), only how confident the prediction is: T > 1 lowers
over-confident scores, T < 1 raises under-confident ones. Guo et al., ICML 2017.

Probabilities are the input. Logits are recovered as log-probabilities (the softmax is unchanged by
adding a constant to every logit), so models that only stored probabilities can be calibrated too.

``export_probabilities`` re-runs the stored checkpoints of the arms whose predictions.csv kept only
the top confidence (photo-only EfficientNet-B0 and the FiLM fusion model) and writes
``probs.csv`` next to predictions.csv: one row per val/test case with ``prob_<class>`` columns. It
checks that the re-run predicts exactly the same class as the stored predictions.

Usage::

    python calibrate.py --export image_only fusion_film      # writes probs.csv per seed
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT, get_dataloaders  # noqa: E402

log = logging.getLogger("calibrate")
EPS = 1e-7


# ------------------------------------------------------------------------------ temperature
def to_logits(prob: np.ndarray) -> np.ndarray:
    return np.log(np.clip(np.asarray(prob, float), EPS, 1.0))


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def nll(logits: np.ndarray, y: np.ndarray, t: float = 1.0) -> float:
    p = softmax(np.asarray(logits, float) / t)
    return float(-np.log(np.clip(p[np.arange(len(y)), y], EPS, 1.0)).mean())


def fit_temperature(logits: np.ndarray, y: np.ndarray, lo: float = 0.05, hi: float = 20.0) -> float:
    """T minimising the validation NLL (golden-section search on log T; the NLL is unimodal in T)."""
    a, b = np.log(lo), np.log(hi)
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = nll(logits, y, np.exp(c)), nll(logits, y, np.exp(d))
    for _ in range(80):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = nll(logits, y, np.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = nll(logits, y, np.exp(d))
    return float(np.exp((a + b) / 2))


def apply_temperature(prob: np.ndarray, t: float) -> np.ndarray:
    return softmax(to_logits(prob) / t)


# --------------------------------------------------------------------- probabilities export
def _model_and_adapt(arm: str, arm_dir: Path, cfg: dict, n_classes: int, ds, device):
    from train import build_fusion
    from dropout_utils import field_index, make_dropout_adapt
    from engine import image_only_adapt
    from models.image_model import SkinImageBaseline

    if arm == "image_only":
        ib = cfg["image_baseline"]
        model = SkinImageBaseline(n_classes, ib["backbone"], False, ib["top_blocks"], ib["drop_rate"])
        return model, image_only_adapt, "img_only"
    model = build_fusion(cfg, n_classes, len(ds.q_cols), len(ds.m_cols))
    adapt = make_dropout_adapt(field_index(ds.q_cols, ds.m_cols), {"mode": "none", "p_full": 0.0, "p_field": 0.0})
    return model, adapt, "fusion"


@torch.no_grad()
def export_probabilities(arm: str, seeds: list[int], backbone: str = "efficientnet_b0",
                         balance: str = "weighted_loss") -> None:
    from run_e1 import arm_spec

    arm_dir = arm_spec(arm, backbone, balance)["dir"]
    cfg = yaml.safe_load((arm_dir / "config_used.yaml").read_text(encoding="utf-8"))
    cfg["loader"]["num_workers"] = 0
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for seed in seeds:
        out = arm_dir / f"seed{seed}" / "probs.csv"
        ckpts = sorted((arm_dir / "seed_checkpoints").glob(f"*_seed{seed}.pt"))
        if len(ckpts) != 1:
            raise FileNotFoundError(f"{arm} seed {seed}: expected one checkpoint, found {ckpts}")
        loaders = get_dataloaders(cfg, seed)
        ds = loaders["val"].dataset
        classes = ds.classes
        model, adapt, _ = _model_and_adapt(arm, arm_dir, cfg, len(classes), ds, device)
        model.load_state_dict(torch.load(ckpts[0], map_location=device, weights_only=True))
        model.to(device).eval()
        frames = []
        for split in ("val", "test"):
            rows, probs = [], []
            for batch in loaders[split]:
                inputs = {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in adapt(batch, False).items()}
                with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    z = model(**inputs)
                probs.append(z.float().softmax(1).cpu().numpy())
                ids = batch["case_id"]
                rows += [str(int(i)) for i in ids] if torch.is_tensor(ids) else [str(i) for i in ids]
            p = np.concatenate(probs)
            df = pd.DataFrame({"case_id": [str(c) for c in rows], "split": split})
            for j, c in enumerate(classes):
                df[f"prob_{c}"] = p[:, j].round(7)
            frames.append(df)
        probs_df = pd.concat(frames, ignore_index=True)
        stored = pd.read_csv(arm_dir / f"seed{seed}" / "predictions.csv", dtype={"case_id": str})
        stored = stored[stored["missing_pct"] == 0.0]
        m = stored.merge(probs_df, on=["case_id", "split"], validate="one_to_one")
        pred = np.array(classes)[m[[f"prob_{c}" for c in classes]].to_numpy().argmax(1)]
        agree = (pred == m["pred_label"].to_numpy()).mean()
        if len(m) != len(stored) or agree < 0.995:  # AMP rounding may flip an exact tie, nothing more
            raise RuntimeError(f"{arm} seed {seed}: re-run disagrees with stored predictions ({agree:.3f})")
        probs_df.to_csv(out, index=False)
        log.info("%s seed %d: wrote %s (agreement with stored predictions %.3f)", arm, seed, out.name, agree)
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--export", nargs="+", default=["image_only", "fusion_film"])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for arm in args.export:
        export_probabilities(arm, args.seeds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
