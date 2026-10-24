"""Task 4.3: Grad-CAM explanations for the app model (DINOv2 + linear probe) and the fine-tuned EfficientNet-B0.

Grad-CAM (Selvaraju et al., ICCV 2017) weights the feature maps of one layer by the gradient of the
predicted class score and keeps the positive part: a coarse heatmap of the image regions that raised
that score. Layers: the last convolution (``conv_head``) of EfficientNet-B0; for the Vision
Transformer, the input norm of the last block, with the patch tokens reshaped back to their grid.

For every test case of every seed the script stores, for the predicted class:
  outcome          correct / wrong / abstained (calibrated confidence below the E4 tau of the seed)
  top10_share      share of the heatmap mass in its 10% hottest pixels (how focused the map is)
  pad_ratio        heatmap mass per pixel on the black letterbox padding, relative to the mean per
                   pixel (1 = no preference; well above 1 = the model looks at the padding, a shortcut)
  rho_head         Spearman correlation between the map of the trained model and the map after the
                   classifier weights are replaced by random ones
  rho_top          the same after also randomizing the top of the encoder (last 4 ViT blocks or the
                   last 2 EfficientNet stages and conv_head)
The two correlations are the model-randomization sanity check of Adebayo et al. (NeurIPS 2018): a
map that stays the same when the weights it should explain are destroyed explains nothing.

Outputs: ``results/gradcam/gradcam_cases.csv`` (no images, only ids and numbers),
``results/gradcam/gradcam_summary.md``; overlay grids of sampled correct / wrong / abstained cases
per eFST group in ``runs/gradcam/`` (git-ignored: they show SCIN photos, which are not redistributed).

Usage::

    python run_gradcam.py                     # both models, seeds 0-9
    python run_gradcam.py --models probe_dinov2 --seeds 0
"""
from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT, SCINDataset  # noqa: E402
from foundation_probe import load_encoder, primary_view  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from run_e1 import PROBES, arm_spec  # noqa: E402
from skinconcern.metrics import efst_group  # noqa: E402

log = logging.getLogger("run_gradcam")
MODELS = ["probe_dinov2", "image_only"]
LABEL = {"probe_dinov2": "DINOv2 + linear probe", "image_only": "EfficientNet-B0 fine-tuned"}
CFG = ROOT / "runs" / "e1_image_only" / "efficientnet_b0_weighted_loss" / "config_used.yaml"


class ProbeModel(nn.Module):
    """Frozen encoder -> standardisation -> linear probe, as one differentiable model."""

    def __init__(self, encoder: nn.Module, probe: dict):
        super().__init__()
        self.encoder = encoder
        self.register_buffer("mu", probe["mean"].float())
        self.register_buffer("sd", probe["std"].float())
        self.head = nn.Linear(self.mu.numel(), len(probe["classes"]))
        self.head.load_state_dict(probe["state_dict"])

    def forward(self, x):
        return self.head((self.encoder(x) - self.mu) / self.sd)


def vit_reshape(grid: int, prefix: int):
    def f(t):
        t = t[:, prefix:, :]
        return t.reshape(t.size(0), grid, grid, t.size(2)).permute(0, 3, 1, 2)
    return f


def build(model_name: str, seed: int, cfg: dict, device):
    """Model, target layer, reshape transform, dataset config, and the parts randomised by the sanity check."""
    if model_name == "image_only":
        ib = cfg["image_baseline"]
        m = SkinImageBaseline(len(cfg["data"]["classes"]), ib["backbone"], False, ib["top_blocks"], ib["drop_rate"])
        ckpt = arm_spec("image_only", "efficientnet_b0", "weighted_loss")["dir"] / "seed_checkpoints" / f"img_only_seed{seed}.pt"
        m.load_state_dict(torch.load(ckpt, map_location="cpu", weights_only=True))
        m.requires_grad_(True)  # Grad-CAM needs a graph; nothing is trained here
        return (m.to(device).eval(), [m.net.conv_head], None, cfg,
                {"head": [m.net.get_classifier()], "top": [m.net.get_classifier(), m.net.conv_head, *m.net.blocks[-2:]]})
    spec, weights = PROBES[model_name]
    enc = load_encoder(spec, weights, device)
    probe = torch.load(arm_spec(model_name, "efficientnet_b0", "weighted_loss")["dir"] / f"probe_seed{seed}.pt",
                       map_location="cpu", weights_only=True)
    m = ProbeModel(enc.model, probe).to(device).eval().requires_grad_(True)  # graph for Grad-CAM only
    ecfg = copy.deepcopy(cfg)
    ecfg["data"]["image_size"] = enc.image_size
    ecfg["normalize"] = {"mean": list(enc.mean), "std": list(enc.std)}
    vit = enc.model
    return (m, [vit.blocks[-1].norm1], vit_reshape(vit.patch_embed.grid_size[0], vit.num_prefix_tokens), ecfg,
            {"head": [m.head], "top": [m.head, *vit.blocks[-4:]]})


def randomised(model: nn.Module, parts: list[nn.Module], seed: int) -> nn.Module:
    """Deep copy of ``model`` with the parameters of ``parts`` replaced by Gaussian noise of the same std."""
    m = copy.deepcopy(model)
    names = {id(p) for part in parts for p in part.parameters()}
    g = torch.Generator().manual_seed(seed)
    for p_new, p_old in zip(m.parameters(), model.parameters()):
        if id(p_old) in names:
            std = p_old.detach().float().std().item() if p_old.numel() > 1 else 0.02
            p_new.data = (torch.randn(p_new.shape, generator=g) * (std or 0.02)).to(p_new.device, p_new.dtype)
    return m


def cams(model, layers, reshape, x, targets):
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

    with GradCAM(model=model, target_layers=layers, reshape_transform=reshape) as cam:
        return cam(input_tensor=x, targets=[ClassifierOutputTarget(int(t)) for t in targets])


def rho(a: np.ndarray, b: np.ndarray, step: int = 8) -> float:
    a, b = a[::step, ::step].ravel(), b[::step, ::step].ravel()
    if a.std() == 0 or b.std() == 0:
        return float("nan")
    return float(stats.spearmanr(a, b).statistic)


def run_model(model_name: str, seeds: list[int], cal: pd.DataFrame, device, out_runs: Path, n_grid: int,
              batch_size: int = 4) -> pd.DataFrame:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    cfg["loader"]["num_workers"] = 0
    arm = model_name
    rows = []
    for seed in seeds:
        model, layers, reshape, dcfg, parts = build(model_name, seed, cfg, device)
        rand = {k: randomised(model, v, 1000 + seed) for k, v in parts.items()}
        ds = primary_view(SCINDataset(dcfg, "test", seed), dcfg)
        loader = torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=2)
        c = cal[(cal["arm"] == arm) & (cal["seed"] == str(seed))].iloc[0]
        t, tau = float(c["T"]), float(c["tau"])
        mean = torch.tensor(dcfg["normalize"]["mean"]).view(1, 3, 1, 1)
        std = torch.tensor(dcfg["normalize"]["std"]).view(1, 3, 1, 1)
        pad_val = (-mean / std)  # normalised value of a black padding pixel
        grid_items = []
        for b in loader:
            x = b["image"].to(device)
            with torch.no_grad():
                p = (model(x).float() / t).softmax(1).cpu()
            conf, pred = p.max(1)
            heat = cams(model, layers, reshape, x, pred)
            heat_h = cams(rand["head"], [rand["head"].net.conv_head] if model_name == "image_only"
                          else [rand["head"].encoder.blocks[-1].norm1], reshape, x, pred)
            heat_t = cams(rand["top"], [rand["top"].net.conv_head] if model_name == "image_only"
                          else [rand["top"].encoder.blocks[-1].norm1], reshape, x, pred)
            pad = torch.isclose(b["image"], pad_val.expand_as(b["image"]), atol=1e-3).all(1).numpy()
            for i in range(len(x)):
                h = heat[i]
                mass = h.sum()
                k = max(1, int(0.1 * h.size))
                top10 = np.sort(h.ravel())[-k:].sum() / mass if mass > 0 else np.nan
                pr = pad[i].mean()
                pad_ratio = (h[pad[i]].sum() / mass) / pr if mass > 0 and pr > 0 else np.nan
                correct = int(pred[i]) == int(b["label"][i])
                outcome = "abstained" if conf[i] < tau else ("correct" if correct else "wrong")
                cid = b["case_id"][i]
                rows.append({"model": model_name, "seed": seed, "case_id": str(int(cid)) if torch.is_tensor(cid) else str(cid),
                             "eFST_group": efst_group(int(b["eFST"][i])), "true": ds.classes[int(b["label"][i])],
                             "pred": ds.classes[int(pred[i])], "confidence": float(conf[i]), "outcome": outcome,
                             "top10_share": float(top10), "pad_ratio": float(pad_ratio) if pr > 0 else np.nan,
                             "pad_fraction": float(pr), "rho_head": rho(h, heat_h[i]), "rho_top": rho(h, heat_t[i])})
                if seed == seeds[0]:
                    img = (b["image"][i:i + 1] * std + mean).clamp(0, 1)[0].permute(1, 2, 0).numpy()
                    grid_items.append((rows[-1], img, h))
        if seed == seeds[0]:
            save_grid(model_name, grid_items, out_runs, n_grid)
        log.info("%s seed %d: %d cases, mean rho head %.2f, top %.2f", model_name, seed, len(ds),
                 np.nanmean([r["rho_head"] for r in rows if r["seed"] == seed]),
                 np.nanmean([r["rho_top"] for r in rows if r["seed"] == seed]))
        del model, rand
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return pd.DataFrame(rows)


def save_grid(model_name: str, items, out: Path, n: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pytorch_grad_cam.utils.image import show_cam_on_image

    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for outcome in ("correct", "wrong", "abstained"):
        fig, axes = plt.subplots(3, n, figsize=(2.2 * n, 7))
        for r, g in enumerate(("I-II", "III-IV", "V-VI")):
            pool = [it for it in items if it[0]["outcome"] == outcome and it[0]["eFST_group"] == g]
            pick = [pool[j] for j in rng.permutation(len(pool))[:n]]
            for c in range(n):
                ax = axes[r, c]
                ax.axis("off")
                if c < len(pick):
                    row, img, h = pick[c]
                    ax.imshow(show_cam_on_image(img.astype(np.float32), h, use_rgb=True))
                    ax.set_title(f"{g}: {row['true'][:9]} -> {row['pred'][:9]}\nconf {row['confidence']:.2f}", fontsize=7)
        fig.suptitle(f"{LABEL[model_name]}: {outcome} cases (seed 0)", fontsize=10)
        fig.tight_layout()
        fig.savefig(out / f"gradcam_grid_{model_name}_{outcome}.png", dpi=120)
        plt.close(fig)


def summary(df: pd.DataFrame, seeds) -> str:
    def f(x):
        return f"{np.nanmean(x):.2f} ± {np.nanstd(x, ddof=1):.2f}"

    out = ["# Task 4.3: Grad-CAM sanity checks and map statistics", "",
           f"Seeds {seeds}, SCIN test split, heatmap of the predicted class. Mean ± sd over cases.", "",
           "## Model-randomization check (Spearman correlation with the trained model's map; near 0 = the map "
           "depends on the learned weights, as it should)", "",
           "| Model | classifier randomised | classifier + top of encoder randomised | top-10% mass share | padding ratio |",
           "|---|---|---|---|---|"]
    for m in df["model"].unique():
        d = df[df.model == m]
        out.append(f"| {LABEL[m]} | {f(d.rho_head)} | {f(d.rho_top)} | {f(d.top10_share)} | {f(d.pad_ratio)} |")
    out += ["", "Padding ratio: heatmap mass per padding pixel relative to the image average (1 = no preference); "
            "computed on cases with letterbox padding only.", "",
            "## Map statistics by outcome and eFST group (top-10% mass share)", "",
            "| Model | outcome | I-II | III-IV | V-VI | cases (I-II / III-IV / V-VI) |", "|---|---|---|---|---|---|"]
    for m in df["model"].unique():
        for o in ("correct", "wrong", "abstained"):
            d = df[(df.model == m) & (df.outcome == o)]
            cells = [f"{d[d.eFST_group == g].top10_share.mean():.3f}" for g in ("I-II", "III-IV", "V-VI")]
            ns = " / ".join(str((d.eFST_group == g).sum()) for g in ("I-II", "III-IV", "V-VI"))
            out.append(f"| {LABEL[m]} | {o} | " + " | ".join(cells) + f" | {ns} |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", nargs="+", default=MODELS, choices=MODELS)
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--n-grid", type=int, default=5, help="examples per row in the overlay grids")
    ap.add_argument("--batch-size", type=int, default=4, help="small: the ViT at 518 px keeps large attention maps")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "gradcam")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cal = pd.read_csv(ROOT / "results" / "e4" / "e4_calibration.csv", dtype={"seed": str})
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = pd.concat([run_model(m, args.seeds, cal, device, ROOT / "runs" / "gradcam", args.n_grid, args.batch_size)
                    for m in args.models],
                   ignore_index=True)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_dir / "gradcam_cases.csv", index=False)
    (args.out_dir / "gradcam_summary.md").write_text(summary(df, args.seeds), encoding="utf-8")
    log.info("wrote %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
