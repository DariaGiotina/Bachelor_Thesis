"""E5 baseline: linear probe on a frozen (foundation) image encoder, trained on the SCIN train split.

The encoder is never trained. Its features are extracted once for every used SCIN case (primary
image, letterbox to the encoder's input size, the encoder's own normalisation, no augmentation) and
cached; then, for each split seed, a single linear layer is trained on the train cases'
standardised features with class-weighted cross-entropy (the same imbalance correction as the
``weighted_loss`` image-only arm) and an L2 penalty. The L2 strength is picked on validation macro-F1 from a small
grid, and the chosen probe is tested once. Predictions go through evaluate.py and the seeds are
summarised as mean +- sd (``foundation_probe_test.csv``), like ``run_image_only.py``.

Backbones (``--backbone``), all loaded through one interface (``load_encoder``):
  timm:<model name>       any timm model, pooled features (``num_classes=0``);
                          ``--weights file.pt`` loads a local checkpoint into it (e.g. PanDerm ViT
                          weights into ``timm:vit_large_patch16_224``)
  open_clip:<model id>    image tower of an OpenCLIP model, e.g.
                          ``open_clip:hf-hub:redlessone/DermLIP_ViT-B-16`` (DermLIP; ``pip install open_clip_torch``)
  hf:<model id>           Hugging Face ``transformers`` vision model (pooled output, else the CLS token)

Outputs in ``runs/foundation_probe/<backbone tag>/`` (git-ignored): features.pt (cache),
seed{k}/predictions.csv + evaluate.py metrics, probe_seed{k}.pt (linear layer, feature mean/std,
classes, backbone), probe_runs.csv, foundation_probe_test.csv.

Usage::

    python foundation_probe.py --backbone timm:vit_base_patch16_224.augreg2_in21k_ft_in1k
    python foundation_probe.py --backbone open_clip:hf-hub:redlessone/DermLIP_ViT-B-16
    python foundation_probe.py --backbone timm:vit_large_patch16_224 --weights panderm_large.pth
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import ConcatDataset, DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, SCINDataset, build_transform, load_config  # noqa: E402
from losses import class_weights  # noqa: E402
from run_image_only import aggregate_seeds  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("foundation_probe")
OPENAI_MEAN, OPENAI_STD = (0.48145466, 0.4578275, 0.40821073), (0.26862954, 0.26130258, 0.27577711)


# --------------------------------------------------------------------------------------- encoders
@dataclass
class Encoder:
    """A frozen image encoder: ``forward(images) -> (batch, dim)`` and its input preprocessing."""
    model: nn.Module
    forward: callable
    image_size: int
    mean: tuple
    std: tuple
    dim: int


def _load_local_weights(model: nn.Module, path: Path) -> None:
    """Load a checkpoint into ``model``, tolerating wrapper keys and prefixes; refuse a poor match."""
    sd = torch.load(path, map_location="cpu", weights_only=False)
    for key in ("model", "state_dict", "model_state", "teacher"):
        if isinstance(sd, dict) and key in sd and isinstance(sd[key], dict):
            sd = sd[key]
    sd = {re.sub(r"^(module\.|encoder\.|backbone\.|visual\.)+", "", k): v for k, v in sd.items()}
    own = model.state_dict()
    usable = {k: v for k, v in sd.items() if k in own and own[k].shape == v.shape}
    if len(usable) < 0.5 * len(own):
        raise ValueError(f"{path.name}: only {len(usable)} of {len(own)} tensors match the model; "
                         "wrong architecture for these weights?")
    model.load_state_dict(usable, strict=False)
    log.info("loaded %d/%d tensors from %s (%d not used)", len(usable), len(own), path.name, len(sd) - len(usable))


def load_encoder(spec: str, weights: Path | None = None, device: torch.device = torch.device("cpu")) -> Encoder:
    """Build a frozen encoder from ``timm:``, ``open_clip:`` or ``hf:`` (see module docstring)."""
    kind, _, name = spec.partition(":")
    if kind == "timm":
        import timm
        model = timm.create_model(name, pretrained=weights is None, num_classes=0)
        if weights is not None:
            _load_local_weights(model, Path(weights))
        dc = timm.data.resolve_model_data_config(model)
        size, mean, std = dc["input_size"][-1], tuple(dc["mean"]), tuple(dc["std"])
        fwd = model
    elif kind == "open_clip":
        import open_clip
        model, _ = open_clip.create_model_from_pretrained(name)
        pc = getattr(model.visual, "preprocess_cfg", {}) or {}
        mean, std = tuple(pc.get("mean", OPENAI_MEAN)), tuple(pc.get("std", OPENAI_STD))
        size = model.visual.image_size
        size = size[0] if isinstance(size, (tuple, list)) else int(size)
        fwd = model.encode_image
    elif kind == "hf":
        from transformers import AutoImageProcessor, AutoModel
        model = AutoModel.from_pretrained(name)
        proc = AutoImageProcessor.from_pretrained(name)
        mean, std = tuple(proc.image_mean), tuple(proc.image_std)
        s = proc.size
        size = (s.get("shortest_edge") or s.get("height")) if isinstance(s, dict) else int(s)

        def fwd(x):
            out = model(pixel_values=x)
            pooled = getattr(out, "pooler_output", None)
            return pooled if pooled is not None else out.last_hidden_state[:, 0]
    else:
        raise ValueError(f"backbone must start with timm:, open_clip: or hf:, got {spec!r}")
    model.eval().requires_grad_(False).to(device)
    with torch.no_grad():
        dim = fwd(torch.zeros(1, 3, size, size, device=device)).shape[-1]
    return Encoder(model, fwd, int(size), mean, std, int(dim))


def backbone_tag(spec: str, weights: Path | None) -> str:
    tag = re.sub(r"[^A-Za-z0-9._-]+", "_", spec).strip("_")
    return f"{tag}__{Path(weights).stem}" if weights else tag


# ------------------------------------------------------------------------------------ features
def primary_view(ds: SCINDataset, cfg: dict) -> SCINDataset:
    """Read any split like val/test: primary image, no augmentation (frozen features need no randomness)."""
    ds.split = "val"  # SCINDataset only randomises the image choice and augmentation for 'train'
    ds.transform = build_transform(cfg, train=False)
    return ds


@torch.no_grad()
def extract_features(enc: Encoder, cfg: dict, device: torch.device, batch_size: int, num_workers: int,
                     only_available: bool) -> dict:
    """Features of every used SCIN case (the three splits of seed 0 hold all of them)."""
    ecfg = copy.deepcopy(cfg)
    ecfg["data"]["image_size"] = enc.image_size
    ecfg["normalize"] = {"mean": list(enc.mean), "std": list(enc.std)}
    parts = [primary_view(SCINDataset(ecfg, s, 0, only_available), ecfg) for s in ("train", "val", "test")]
    loader = DataLoader(ConcatDataset(parts), batch_size=batch_size, shuffle=False, num_workers=num_workers,
                        pin_memory=device.type == "cuda")
    feats, ids, labels, efst, emst, failed = [], [], [], [], [], 0
    for b in loader:
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            f = enc.forward(b["image"].to(device, non_blocking=True))
        feats.append(f.float().cpu())
        ids += [str(int(i)) for i in b["case_id"]]
        labels.append(b["label"])
        efst.append(b["eFST"])
        emst.append(b["eMST"])
        failed += int((b["image_ok"] == 0).sum())
    if failed:
        log.warning("%d cases had no readable image (black image features)", failed)
    out = {"features": torch.cat(feats), "case_id": ids, "label": torch.cat(labels), "eFST": torch.cat(efst),
           "eMST": torch.cat(emst), "classes": parts[0].classes, "dim": enc.dim}
    if len(set(ids)) != len(ids):
        raise ValueError("a case appears in two splits of seed 0")
    return out


# ------------------------------------------------------------------------------------------ probe
def train_probe(x_tr, y_tr, x_va, y_va, n_classes: int, l2: float, lr: float, epochs: int,
                patience: int, device: torch.device, seed: int) -> tuple[nn.Linear, float, int]:
    """Multinomial logistic regression: full-batch Adam on one linear layer with an L2 penalty on its
    weights (not the bias); keeps the step with the best validation macro-F1."""
    torch.manual_seed(seed)
    probe = nn.Linear(x_tr.shape[1], n_classes).to(device)
    opt = torch.optim.Adam(probe.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights(y_tr.cpu().numpy(), n_classes).to(device))
    labels_va = np.unique(y_va.cpu().numpy())
    best, best_ep, best_state, bad = -1.0, -1, None, 0
    for ep in range(epochs):
        probe.train()
        opt.zero_grad(set_to_none=True)
        (loss_fn(probe(x_tr), y_tr) + l2 * probe.weight.pow(2).sum()).backward()
        opt.step()
        probe.eval()
        with torch.no_grad():
            pred = probe(x_va).argmax(1).cpu().numpy()
        f1 = f1_score(y_va.cpu().numpy(), pred, labels=labels_va, average="macro", zero_division=0)
        if f1 > best:
            best, best_ep, bad = f1, ep, 0
            best_state = {k: v.detach().clone() for k, v in probe.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    probe.load_state_dict(best_state)
    return probe, float(best), best_ep


def predictions(probe: nn.Linear, x, idx: np.ndarray, feats: dict, split: str, seed: int) -> pd.DataFrame:
    with torch.no_grad():
        prob = probe(x).float().softmax(1).cpu()
    conf, pred = prob.max(1)
    classes = feats["classes"]
    tone = lambda t: pd.Series(t[idx].numpy()).where(lambda s: s > 0).astype("Int64")  # noqa: E731
    df = pd.DataFrame({"case_id": [feats["case_id"][i] for i in idx], "split": split,
                       "true_label": [classes[i] for i in feats["label"][idx].numpy()],
                       "pred_label": [classes[i] for i in pred.numpy()], "confidence": conf.numpy().round(6),
                       "eFST": tone(feats["eFST"]), "eMST": tone(feats["eMST"]), "seed": seed, "missing_pct": 0.0})
    for j, c in enumerate(classes):
        df[f"prob_{c}"] = prob[:, j].numpy().round(6)
    return df


# ------------------------------------------------------------------------------------------- main
def run(args) -> pd.DataFrame:
    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    root = args.out_root / backbone_tag(args.backbone, args.weights)
    root.mkdir(parents=True, exist_ok=True)
    cache = root / "features.pt"
    if cache.exists() and not args.refresh_features:
        feats = torch.load(cache, weights_only=False)
        if feats["classes"] != list(cfg["data"]["classes"]):
            raise ValueError(f"{cache} was built for classes {feats['classes']}; use --refresh-features")
        log.info("features from cache %s (%d cases, dim %d)", cache, len(feats["case_id"]), feats["dim"])
    else:
        enc = load_encoder(args.backbone, args.weights, device)
        log.info("encoder %s: dim %d, input %d px, mean %s std %s", args.backbone, enc.dim, enc.image_size,
                 enc.mean, enc.std)
        feats = extract_features(enc, cfg, device, args.batch_size, args.num_workers, args.only_available)
        torch.save(feats, cache)
        del enc
    pos = {c: i for i, c in enumerate(feats["case_id"])}
    x_all, y_all = feats["features"], feats["label"]
    n_classes = len(feats["classes"])
    split_ids = json.loads((ROOT / cfg["paths"]["splits"]).read_text(encoding="utf-8"))

    runs, flats = [], []
    for seed in args.seeds:
        seed_everything(seed)
        # split lists also hold cases dropped by the dataset (label "excluded"); only used cases have features
        idx = {s: np.array([pos[c] for c in split_ids[str(seed)][s] if c in pos]) for s in ("train", "val", "test")}
        if sum(map(len, idx.values())) != len(pos):
            raise ValueError(f"seed {seed} splits do not cover the cached cases; use --refresh-features")
        mu, sd = x_all[idx["train"]].mean(0), x_all[idx["train"]].std(0).clamp_min(1e-6)  # train statistics only
        x = {s: ((x_all[i] - mu) / sd).to(device) for s, i in idx.items()}
        y = {s: y_all[i].to(device) for s, i in idx.items()}
        trials = [(wd, *train_probe(x["train"], y["train"], x["val"], y["val"], n_classes, wd, args.lr,
                                     args.epochs, args.patience, device, seed)) for wd in args.l2]
        wd, probe, val_f1, best_ep = max(trials, key=lambda t: t[2])
        log.info("seed %d: L2 %.0e chosen (val macro-F1 %.3f at epoch %d; grid %s)", seed, wd, val_f1,
                 best_ep, {f"{t[0]:.0e}": round(t[2], 3) for t in trials})
        if wd == max(args.l2) and len(args.l2) > 1:
            log.warning("seed %d: the largest L2 was chosen; consider extending --l2", seed)
        out = root / f"seed{seed}"
        out.mkdir(exist_ok=True)
        torch.save({"state_dict": probe.state_dict(), "mean": mu, "std": sd, "classes": feats["classes"],
                    "backbone": args.backbone, "weights": str(args.weights) if args.weights else None,
                    "l2": wd}, root / f"probe_seed{seed}.pt")
        pd.concat([predictions(probe, x[s], idx[s], feats, s, seed) for s in ("val", "test")],
                  ignore_index=True).to_csv(out / "predictions.csv", index=False)
        harness.main([str(out / "predictions.csv"), "--split", "test", "--n-boot", str(args.n_boot)])
        flats.append(pd.read_csv(out / "metrics_summary.csv", dtype={"seed": str}))
        runs.append({"seed": seed, "backbone": args.backbone, "l2": wd, "best_epoch": best_ep,
                     "val_macro_f1": val_f1, "n_train": len(idx["train"]), "n_val": len(idx["val"]),
                     "n_test": len(idx["test"])})
        pd.DataFrame(runs).to_csv(root / "probe_runs.csv", index=False)

    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    summary.insert(0, "experiment", "E5_linear_probe")
    summary.insert(1, "backbone", args.backbone)
    summary.to_csv(root / "foundation_probe_test.csv", index=False)
    for _, r in summary[(summary["scope"] == "overall") & summary["metric"].isin(["macro_f1", "balanced_acc"])].iterrows():
        log.info("test %-12s %s (n_seeds=%d)", r["metric"], r["mean_pm_sd"], r["n_seeds"])
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backbone", default="timm:vit_base_patch16_224.augreg2_in21k_ft_in1k",
                    help="timm:<name> | open_clip:<id> | hf:<id>")
    ap.add_argument("--weights", type=Path, default=None, help="local checkpoint for a timm backbone (e.g. PanDerm)")
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "foundation_probe")
    ap.add_argument("--l2", type=float, nargs="+", default=[0.0, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0],
                    help="L2 penalties tried; the best on validation macro-F1 is kept")
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--epochs", type=int, default=2000, help="full-batch steps")
    ap.add_argument("--patience", type=int, default=200)
    ap.add_argument("--batch-size", type=int, default=64, help="feature extraction batch size")
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--only-available", action="store_true", help="skip cases whose images are missing")
    ap.add_argument("--refresh-features", action="store_true", help="re-extract features instead of the cache")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
