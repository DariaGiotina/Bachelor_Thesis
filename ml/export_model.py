"""Task 4.5: export the app model to ONNX, with its temperature, tau and out-of-scope filter.

The app model chosen after E4 is the frozen DINOv2 ViT-B/14 encoder + the linear probe (E5), trained
on SCIN only. The exported model is the probe of one split seed (``--seed``, default 0: the
development seed, fixed by rule, not picked for its test score), so the shipped model is exactly one
of the models whose test results are in the tables. Its expected performance is the 10-seed mean of
the tables, not the result of this one seed.

Steps:
  1. Features of the seed's train / val / test cases in full precision (fp32) with the same
     preprocessing as evaluation; compared with the cached (mixed-precision) features of E5.
  2. On validation: temperature T (NLL), tau for the target coverage (80%) and the kNN threshold
     (95th percentile, k = 10), exactly as ``run_e4.py`` and ``ood_detect.py`` do, but from the fp32
     features the app will compute. The bank of the kNN filter is the seed's L2-normalised train features.
  3. One ``torch.nn.Module`` (pixel normalisation, encoder, standardisation, probe, division by T,
     softmax, kNN score) exported to ONNX with a dynamic batch size and checked with ``onnx.checker``.
  4. ONNX Runtime on the seed's test images: outputs vs PyTorch (largest absolute difference), class
     agreement with the stored E5 predictions, and the test metrics vs the stored E4 numbers.

Outputs: ``export/skin_concern_dinov2.onnx`` (git-ignored, about 350 MB), ``export/skin_concern_dinov2.json``
(classes, T, tau, kNN threshold, preprocessing, check results, SHA-256 of the ONNX file) and
``results/export/export_check.md``. Inference: ``serving.py``.

Usage::

    python export_model.py                 # seed 0, opset 18
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import foundation_probe as fp  # noqa: E402
from abstain import choose_tau  # noqa: E402
from calibrate import fit_temperature  # noqa: E402
from data_loading import ROOT, SCINDataset, load_config  # noqa: E402
from ood_detect import K, PROBE_DIR, knn_score, l2n, threshold  # noqa: E402
from skinconcern.metrics import macro_f1  # noqa: E402

log = logging.getLogger("export_model")
BACKBONE = "timm:vit_base_patch14_dinov2.lvd142m"
OUT = ROOT / "export" / "skin_concern_dinov2.onnx"


class AppModel(nn.Module):
    """Letterboxed RGB photo (0-255) -> calibrated class probabilities and the kNN score."""

    def __init__(self, encoder: nn.Module, probe: dict, mean: tuple, std: tuple, temperature: float,
                 bank: torch.Tensor, k: int = K):
        super().__init__()
        self.encoder = encoder
        self.linear = nn.Linear(probe["state_dict"]["weight"].shape[1], probe["state_dict"]["weight"].shape[0])
        self.linear.load_state_dict({k_: v.cpu() for k_, v in probe["state_dict"].items()})
        self.register_buffer("pix_mean", torch.tensor(mean).view(1, 3, 1, 1) * 255)
        self.register_buffer("pix_std", torch.tensor(std).view(1, 3, 1, 1) * 255)
        self.register_buffer("feat_mean", probe["mean"].cpu().float())
        self.register_buffer("feat_std", probe["std"].cpu().float())
        self.register_buffer("temperature", torch.tensor(float(temperature)))
        self.register_buffer("bank", bank.float())  # L2-normalised train features, (n_train, dim)
        self.k = k

    def features(self, image: torch.Tensor) -> torch.Tensor:
        return self.encoder((image - self.pix_mean) / self.pix_std)

    def heads(self, f: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        prob = (self.linear((f - self.feat_mean) / self.feat_std) / self.temperature).softmax(-1)
        sim = (f / f.norm(dim=1, keepdim=True).clamp_min(1e-12)) @ self.bank.T
        knn = 1 - sim.topk(self.k, dim=1).values[:, -1]
        return prob, knn

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.heads(self.features(image))


# ------------------------------------------------------------------------------------ helpers
def scin_loader(cfg: dict, split: str, seed: int, size: int, batch_size: int) -> DataLoader:
    """The seed's split, primary image, evaluation transform, pixels left at 0-255 (the model normalises)."""
    ecfg = copy.deepcopy(cfg)
    ecfg["data"]["image_size"] = size
    ecfg["normalize"] = {"mean": [0.0, 0.0, 0.0], "std": [1 / 255] * 3}
    ds = fp.primary_view(SCINDataset(ecfg, split, seed), ecfg)
    return DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0)


@torch.no_grad()
def encode(model: AppModel, loader: DataLoader, device: torch.device) -> dict:
    feats, ids, labels, efst, emst, images = [], [], [], [], [], []
    for b in loader:
        if (b["image_ok"] == 0).any():
            raise RuntimeError("a case has no readable image; the export needs every image")
        feats.append(model.features(b["image"].to(device).float()).cpu())
        ids += [str(int(i)) for i in b["case_id"]]
        labels.append(b["label"])
        efst.append(b["eFST"])
        emst.append(b["eMST"])
    return {"features": torch.cat(feats), "case_id": ids, "label": torch.cat(labels).numpy(),
            "eFST": torch.cat(efst).numpy(), "eMST": torch.cat(emst).numpy()}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_onnx(model: AppModel, path: Path, size: int, opset: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    example = torch.zeros(2, 3, size, size)
    batch = torch.export.Dim("batch", min=1, max=64)
    prog = torch.onnx.export(model, (example,), dynamo=True, opset_version=opset, input_names=["image"],
                             output_names=["probabilities", "knn_score"],
                             dynamic_shapes={"image": {0: batch}}, external_data=False, verbose=False)
    prog.save(str(path))
    import onnx
    onnx.checker.check_model(str(path))


def ort_outputs(path: Path, loader: DataLoader) -> tuple[np.ndarray, np.ndarray]:
    import onnxruntime as ort
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    probs, knns = [], []
    for b in loader:
        p, k = sess.run(["probabilities", "knn_score"], {"image": b["image"].numpy().astype(np.float32)})
        probs.append(p)
        knns.append(k)
    return np.concatenate(probs), np.concatenate(knns)


def selective_numbers(prob: np.ndarray, y: np.ndarray, tau: float, flag: np.ndarray | None = None) -> dict:
    pred, conf = prob.argmax(1), prob.max(1)
    correct = pred == y
    answered = conf >= tau if flag is None else (conf >= tau) & ~flag
    return {"accuracy": correct.mean(), "macro_f1": macro_f1(y, pred), "coverage": answered.mean(),
            "selective_accuracy": correct[answered].mean()}


# --------------------------------------------------------------------------------------- main
def run(args) -> dict:
    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    probe = torch.load(PROBE_DIR / f"probe_seed{args.seed}.pt", map_location="cpu", weights_only=True)
    if probe["backbone"] != BACKBONE:
        raise ValueError(f"probe_seed{args.seed}.pt belongs to {probe['backbone']}")
    classes = probe["classes"]
    enc = fp.load_encoder(BACKBONE, None, device)
    model = AppModel(enc.model.float(), probe, enc.mean, enc.std, 1.0,
                     torch.zeros(K, enc.dim)).to(device).eval()

    # 1. fp32 features of the seed's three splits
    loaders = {s: scin_loader(cfg, s, args.seed, enc.image_size, args.batch_size) for s in ("train", "val", "test")}
    data = {s: encode(model, ld, device) for s, ld in loaders.items()}
    cache = torch.load(PROBE_DIR / "features.pt", weights_only=False)
    pos = {c: i for i, c in enumerate(cache["case_id"])}
    cos = []
    for d in data.values():
        ref = cache["features"][[pos[c] for c in d["case_id"]]]
        cos.append(torch.nn.functional.cosine_similarity(d["features"], ref, dim=1).numpy())
    cos = np.concatenate(cos)
    log.info("fp32 vs cached features: cosine similarity min %.5f, mean %.6f", cos.min(), cos.mean())

    # 2. T, tau and the kNN threshold on validation, from the fp32 features
    bank = l2n(data["train"]["features"].numpy())
    model.bank = torch.from_numpy(bank).to(device)
    with torch.no_grad():
        val_prob, val_knn = (t.cpu().numpy() for t in model.heads(data["val"]["features"].to(device)))
    t = fit_temperature(np.log(np.clip(val_prob, 1e-7, 1)), data["val"]["label"])
    model.temperature.fill_(t)
    with torch.no_grad():
        val_prob, _ = (x.cpu().numpy() for x in model.heads(data["val"]["features"].to(device)))
        test_prob, test_knn = (x.cpu().numpy() for x in model.heads(data["test"]["features"].to(device)))
    tau = choose_tau(val_prob.max(1), args.coverage)
    knn_thr = threshold(val_knn, args.keep)
    if not np.allclose(knn_score(data["val"]["features"].numpy(), bank, K), val_knn, atol=1e-4):
        raise RuntimeError("the kNN score of the module differs from ood_detect.knn_score")
    stored = pd.read_csv(ROOT / "results" / "e4" / "e4_calibration.csv", dtype={"seed": str})
    stored = stored[(stored["arm"] == "probe_dinov2") & (stored["seed"] == str(args.seed))].iloc[0]
    log.info("T %.4f (stored %.4f), tau %.4f (stored %.4f), kNN threshold %.4f", t, stored["T"], tau,
             stored["tau"], knn_thr)

    # 3. export
    model = model.cpu().eval()
    t0 = time.time()
    export_onnx(model, args.out, enc.image_size, args.opset)
    log.info("exported %s (%.0f MB) in %.0f s", args.out, args.out.stat().st_size / 2**20, time.time() - t0)

    # 4. ONNX Runtime on the test images
    t0 = time.time()
    ort_prob, ort_knn = ort_outputs(args.out, loaders["test"])
    ms_per_image = 1000 * (time.time() - t0) / len(ort_prob)
    y = data["test"]["label"]
    stored_pred = pd.read_csv(PROBE_DIR / f"seed{args.seed}" / "predictions.csv", dtype={"case_id": str})
    stored_pred = stored_pred[stored_pred["split"] == "test"].set_index("case_id").loc[data["test"]["case_id"]]
    agree_stored = float((np.array(classes)[ort_prob.argmax(1)] == stored_pred["pred_label"].to_numpy()).mean())
    flag = ort_knn > knn_thr
    ours, ours_rule = selective_numbers(ort_prob, y, tau), selective_numbers(ort_prob, y, tau, flag)
    check = {
        "feature_cosine_fp32_vs_cached": {"min": float(cos.min()), "mean": float(cos.mean())},
        "onnx_vs_torch_max_abs_diff": {"probabilities": float(np.abs(ort_prob - test_prob).max()),
                                       "knn_score": float(np.abs(ort_knn - test_knn).max())},
        "onnx_vs_torch_class_agreement": float((ort_prob.argmax(1) == test_prob.argmax(1)).mean()),
        "onnx_vs_stored_e5_class_agreement": agree_stored,
        "test_n": int(len(y)),
        "test_exported": {k: float(v) for k, v in ours.items()},
        "test_exported_with_knn_filter": {k: float(v) for k, v in ours_rule.items()},
        "test_knn_flagged": float(flag.mean()),
        "test_stored_e4": {k: float(stored[k]) for k in ("accuracy", "macro_f1", "coverage", "selective_accuracy")},
        "stored_e4_T_tau": {"T": float(stored["T"]), "tau": float(stored["tau"])},
        "onnxruntime_cpu_ms_per_image": round(ms_per_image, 1),
    }
    import onnxruntime
    import timm
    meta = {
        "model": "DINOv2 ViT-B/14 (frozen) + linear probe, SCIN only",
        "intended_use": "informational skin-concern category for the app; not a medical device, no diagnosis",
        "created": date.today().isoformat(),
        "encoder": {"name": BACKBONE.removeprefix("timm:"), "licence": "Apache-2.0", "dim": enc.dim},
        "probe": {"seed": args.seed, "l2": probe["l2"], "file": f"probe_seed{args.seed}.pt"},
        "classes": classes,
        "temperature": t, "tau": tau, "target_coverage": args.coverage,
        "knn": {"k": K, "threshold": knn_thr, "keep": args.keep, "bank_size": int(len(bank))},
        "decision_order": ["unusual_photo if knn_score > knn.threshold",
                           "uncertain if max probability < tau", "answered otherwise"],
        "preprocessing": {"input_size": enc.image_size, "cache_longest_side": 448, "layout": "NCHW RGB float32",
                          "pixel_range": "0-255 (normalised inside the graph)", "mean": list(enc.mean),
                          "std": list(enc.std), "resize": "Lanczos to 448 if larger, bilinear longest side to "
                          f"{enc.image_size}, centred black padding (serving.preprocess)"},
        "inputs": {"image": ["batch", 3, enc.image_size, enc.image_size]},
        "outputs": {"probabilities": ["batch", len(classes)], "knn_score": ["batch"]},
        "opset": args.opset,
        "versions": {"torch": torch.__version__, "timm": timm.__version__, "onnxruntime": onnxruntime.__version__},
        "onnx_sha256": sha256(args.out),
        "check": check,
    }
    args.out.with_suffix(".json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_report(meta, ROOT / "results" / "export" / "export_check.md")
    return meta


def write_report(meta: dict, path: Path) -> None:
    c = meta["check"]
    e, r, s = c["test_exported"], c["test_exported_with_knn_filter"], c["test_stored_e4"]
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    lines = [
        "# Exported app model: check (Task 4.5)", "",
        f"Model: {meta['model']}; probe of split seed {meta['probe']['seed']} (L2 {meta['probe']['l2']}); "
        f"ONNX opset {meta['opset']}; SHA-256 `{meta['onnx_sha256'][:16]}...`.", "",
        f"Calibration fitted on the fp32 validation features: T = {meta['temperature']:.3f} "
        f"(E4 stored {c['stored_e4_T_tau']['T']:.3f}), tau = {meta['tau']:.3f} "
        f"(E4 {c['stored_e4_T_tau']['tau']:.3f}) for {pct(meta['target_coverage'])} coverage; "
        f"kNN threshold {meta['knn']['threshold']:.4f} (k = {meta['knn']['k']}, "
        f"{pct(1 - meta['knn']['keep'])} of validation cases flagged, bank of {meta['knn']['bank_size']} train cases).", "",
        "## Equivalence", "",
        "| Check | Value |", "|---|---|",
        f"| Cosine similarity fp32 vs cached mixed-precision features (min / mean) | "
        f"{c['feature_cosine_fp32_vs_cached']['min']:.5f} / {c['feature_cosine_fp32_vs_cached']['mean']:.6f} |",
        f"| Largest difference ONNX vs PyTorch, probabilities | {c['onnx_vs_torch_max_abs_diff']['probabilities']:.2e} |",
        f"| Largest difference ONNX vs PyTorch, kNN score | {c['onnx_vs_torch_max_abs_diff']['knn_score']:.2e} |",
        f"| Same class ONNX vs PyTorch | {pct(c['onnx_vs_torch_class_agreement'])} |",
        f"| Same class ONNX vs stored E5 predictions | {pct(c['onnx_vs_stored_e5_class_agreement'])} |",
        f"| ONNX Runtime on CPU, ms per image (with reading the photo) | {c['onnxruntime_cpu_ms_per_image']} |", "",
        f"## Test split of seed {meta['probe']['seed']} ({c['test_n']} cases)", "",
        "| | Accuracy | Macro-F1 | Coverage | Selective accuracy |", "|---|---|---|---|---|",
        f"| Stored E4 result | {pct(s['accuracy'])} | {s['macro_f1']:.3f} | {pct(s['coverage'])} | {pct(s['selective_accuracy'])} |",
        f"| Exported model, confidence rule | {pct(e['accuracy'])} | {e['macro_f1']:.3f} | {pct(e['coverage'])} | {pct(e['selective_accuracy'])} |",
        f"| Exported model, kNN filter + confidence | {pct(r['accuracy'])} | {r['macro_f1']:.3f} | {pct(r['coverage'])} | {pct(r['selective_accuracy'])} |",
        "", f"kNN filter flags {pct(c['test_knn_flagged'])} of the test cases.", "",
        "One seed only: the expected performance of the model is the 10-seed mean in the result tables, "
        "not this row.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--coverage", type=float, default=0.8)
    ap.add_argument("--keep", type=float, default=0.95, help="share of validation cases below the kNN threshold")
    ap.add_argument("--opset", type=int, default=18)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
