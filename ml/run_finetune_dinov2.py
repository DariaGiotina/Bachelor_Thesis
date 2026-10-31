"""Task 4.7: DINOv2 ViT-B/14 fine-tuned end to end on SCIN, against the frozen encoder + linear probe.

The app model (Task 4.5) trains only a linear layer on top of the frozen DINOv2 encoder. This
script also trains the encoder, in the two stages of the EfficientNet-B0 baseline:

* the classifier starts from the linear probe of the same split seed (``foundation_probe.py``; its
  feature standardisation is folded into the weights), the "linear probe, then fine-tune" order
  of Kumar et al. (ICLR 2022), so training starts from the probe's predictions;
* stage 1 (``--head-epochs``): encoder frozen, only the head adapts to the training images (any
  image of the case, augmented), which the probe never saw;
* stage 2 (``--epochs``): the top ``--top-blocks`` transformer blocks and the final norm are
  trained too, with layer-wise learning-rate decay (block ``i`` of ``L`` gets
  ``lr * decay ** (L - i)``) and the head at ``head_lr``; biases, norms and the position / class
  tokens get no weight decay;
* AdamW, one warm-up epoch per stage (linear, per step) then cosine decay, class-weighted
  cross-entropy (the ``weighted_loss`` correction of every other arm), the train augmentation of
  ``configs/base.yaml``, mixed precision, gradient clipping;
* batches of 8 images (what fits at 518 px) with the gradients of ``--accum`` batches summed
  before each step, so one step sees 32 cases like the other arms.

Tried first and dropped (validation only, seeds 0-1; logs in ``runs/logs/finetune_*``): the whole
encoder from the first step (lr 2e-5, drop path 0.1, batch 8, then lr 1e-5 with batches of 32).
On seed 1 validation macro-F1 fell from 0.555 to about 0.42-0.45 within two epochs and the
training loss rose from 0.23 to about 1.9: the steps moved the encoder away from features the
head relied on. Stage 2 also dips first and recovers later, so it runs to the end
(``--patience 10``) instead of stopping at the dip.

Input as the probe: 518 px letterbox, ImageNet normalisation, padding ``--pad-mode`` (black or
mirrored). Model selection on validation macro-F1 over the epochs of both stages, with the
starting point (the probe itself, epoch -1) as one of the candidates; the best weights are
tested once, and ``seed_runs.csv`` records which stage won.

Outputs in ``runs/finetune_dinov2/<pad mode>/`` (git-ignored): seed{k}/predictions.csv (val + test,
``prob_<class>`` columns, the format of the probe arms) + evaluate.py metrics, seed{k}/log.csv,
seed_checkpoints/ft_seed{k}.pt, seed_runs.csv, finetune_test.csv.

Usage::

    python run_finetune_dinov2.py --seeds 0 1 2 3 4 5 6 7 8 9
    python run_finetune_dinov2.py --pad-mode reflect --seeds 0
    python run_finetune_dinov2.py --seeds 0 --epochs 1 --max-batches 5 --n-boot 50     # smoke test
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from engine import EarlyStopping  # noqa: E402
from foundation_probe import backbone_tag  # noqa: E402
from losses import class_weights  # noqa: E402
from run_image_only import aggregate_seeds, write_seed_runs  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_finetune_dinov2")
MODEL = "vit_base_patch14_dinov2.lvd142m"
NO_DECAY = ("cls_token", "pos_embed", "reg_token")


# ------------------------------------------------------------------------------------- model
def build_model(n_classes: int, probe: dict, drop_path: float) -> nn.Module:
    """DINOv2 ViT-B/14 with its classifier set to the linear probe ``W ((f - mu) / sd) + b``."""
    model = timm.create_model(MODEL, pretrained=True, num_classes=n_classes, drop_path_rate=drop_path)
    w, b = probe["state_dict"]["weight"].float(), probe["state_dict"]["bias"].float()
    mu, sd = probe["mean"].float(), probe["std"].float()
    with torch.no_grad():
        model.head.weight.copy_(w / sd)
        model.head.bias.copy_(b - (w / sd) @ mu)
    return model


def layer_id(name: str, n_blocks: int) -> int:
    """0 = embeddings, i + 1 = block i, n_blocks + 1 = final norm and head."""
    if name.startswith(("patch_embed", *NO_DECAY)):
        return 0
    if name.startswith("blocks."):
        return int(name.split(".")[1]) + 1
    return n_blocks + 1


def param_groups(model: nn.Module, lr: float, head_lr: float, decay: float, weight_decay: float) -> list[dict]:
    """AdamW groups with layer-wise learning-rate decay; no weight decay on 1-D tensors and tokens."""
    n = len(model.blocks)
    groups: dict[tuple, dict] = {}
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        lid = layer_id(name, n)
        head = name.startswith("head.")
        wd = 0.0 if p.ndim == 1 or name.startswith(NO_DECAY) else weight_decay
        key = ("head" if head else lid, wd)
        g = groups.setdefault(key, {"params": [], "weight_decay": wd, "name": f"{key[0]}_{'decay' if wd else 'no_decay'}",
                                    "lr": head_lr if head else lr * decay ** (n + 1 - lid)})
        g["params"].append(p)
    for g in groups.values():
        g["initial_lr"] = g["lr"]
    return list(groups.values())


def lr_factor(step: int, warmup: int, total: int) -> float:
    """Linear warm-up, then cosine decay to 0."""
    if step < warmup:
        return (step + 1) / warmup
    return 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total - warmup)))


# ---------------------------------------------------------------------------------- training
@torch.no_grad()
def predict(model: nn.Module, loader, device: torch.device, amp: bool, max_batches: int | None = None) -> dict:
    """Class probabilities of every case of ``loader``, with labels, tones and ids."""
    model.eval()
    out = {k: [] for k in ("prob", "label", "eFST", "eMST", "case_id")}
    for b, batch in enumerate(loader):
        if max_batches and b >= max_batches:
            break
        with torch.autocast(device_type=device.type, enabled=amp and device.type == "cuda"):
            logits = model(batch["image"].to(device, non_blocking=True))
        out["prob"].append(logits.float().softmax(1).cpu())
        for k in ("label", "eFST", "eMST", "case_id"):
            out[k].append(batch[k])
    return {k: torch.cat(v).numpy() for k, v in out.items()}


def macro_f1(res: dict) -> float:
    from sklearn.metrics import f1_score
    y = res["label"]
    return float(f1_score(y, res["prob"].argmax(1), labels=np.unique(y), average="macro", zero_division=0))


def frame(res: dict, classes: list[str], split: str, seed: int) -> pd.DataFrame:
    """Predictions in the format of the probe arms (evaluate.py + run_e4.py read it)."""
    prob = res["prob"]
    tone = lambda t: pd.Series(t).where(lambda s: s > 0).astype("Int64")  # noqa: E731
    df = pd.DataFrame({"case_id": res["case_id"].astype(str), "split": split,
                       "true_label": [classes[i] for i in res["label"]],
                       "pred_label": [classes[i] for i in prob.argmax(1)], "confidence": prob.max(1).round(6),
                       "eFST": tone(res["eFST"]), "eMST": tone(res["eMST"]), "seed": seed, "missing_pct": 0.0})
    for j, c in enumerate(classes):
        df[f"prob_{c}"] = prob[:, j].round(6)
    return df


def set_trainable(model: nn.Module, top_blocks: int) -> None:
    """Train the head, plus the final norm and the top ``top_blocks`` blocks (0 = head only)."""
    model.requires_grad_(False)
    model.head.requires_grad_(True)
    if top_blocks:
        model.norm.requires_grad_(True)
        for blk in model.blocks[len(model.blocks) - top_blocks:]:
            blk.requires_grad_(True)


def train_seed(seed: int, cfg: dict, args, out_dir: Path, ckpt: Path, device: torch.device) -> dict:
    seed_everything(seed)
    loaders = get_dataloaders(cfg, seed)
    train_ds = loaders["train"].dataset
    classes, n_classes = train_ds.classes, len(train_ds.classes)
    probe_dir = ROOT / "runs" / "foundation_probe" / backbone_tag(f"timm:{MODEL}", None, args.pad_mode)
    probe = torch.load(probe_dir / f"probe_seed{seed}.pt", map_location="cpu", weights_only=True)
    if probe["classes"] != classes:
        raise ValueError(f"probe classes {probe['classes']} != {classes}")
    model = build_model(n_classes, probe, args.drop_path).to(device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights(train_ds.labels, n_classes).to(device))
    batches = min(len(loaders["train"]), args.max_batches or len(loaders["train"]))
    steps = math.ceil(batches / args.accum)  # optimizer steps per epoch
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    stopper, history, t0, epoch = EarlyStopping(args.patience), [], time.time(), 0

    def validate(stage: int, train_loss: float, secs: float, lrs: dict) -> None:
        val = predict(model, loaders["val"], device, True, args.max_batches)
        f1 = macro_f1(val)
        history.append({"epoch": epoch - 1 if stage < 0 else epoch, "stage": stage, "train_loss": train_loss,
                        "val_macro_f1": f1, "epoch_time": round(secs, 1), **lrs})
        pd.DataFrame(history).to_csv(out_dir / "log.csv", index=False)
        if stopper.step(f1, history[-1]["epoch"]):
            torch.save(model.state_dict(), ckpt)
        log.info("seed %d stage %d epoch %d train %.4f val macro-F1 %.3f%s (%.0fs)", seed, stage, history[-1]["epoch"],
                 train_loss, f1, " *" if stopper.best_epoch == history[-1]["epoch"] else "", secs)

    validate(-1, float("nan"), 0.0, {})  # the probe itself: fine-tuning has to beat it on validation
    for stage, n_epochs, top in ((1, args.head_epochs, 0), (2, args.epochs, args.top_blocks)):
        if n_epochs == 0:
            continue
        model.load_state_dict(torch.load(ckpt, map_location=device, weights_only=True))  # best so far
        set_trainable(model, top)
        opt = torch.optim.AdamW(param_groups(model, args.lr, args.head_lr, args.layer_decay, args.weight_decay))
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: lr_factor(s, steps, steps * n_epochs))
        stopper.bad_epochs = 0  # own patience per stage
        log.info("seed %d stage %d: %d trainable parameters", seed, stage,
                 sum(p.numel() for p in model.parameters() if p.requires_grad))
        for _ in range(n_epochs):
            train_ds.set_epoch(epoch)
            model.train()
            total, n, e0 = 0.0, 0, time.time()
            lrs = {"lr_head": max(g["initial_lr"] for g in opt.param_groups if g["name"].startswith("head")),
                   "lr_top_block": max((g["initial_lr"] for g in opt.param_groups if not g["name"].startswith("head")),
                                       default=0.0)}
            opt.zero_grad(set_to_none=True)
            for b, batch in enumerate(loaders["train"]):
                if b >= batches:
                    break
                x, y = batch["image"].to(device, non_blocking=True), batch["label"].to(device, non_blocking=True)
                with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    loss = loss_fn(model(x), y)
                scaler.scale(loss / args.accum).backward()
                total, n = total + loss.item() * len(y), n + len(y)
                if (b + 1) % args.accum == 0 or b + 1 == batches:
                    scaler.unscale_(opt)
                    nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], args.grad_clip)
                    scaler.step(opt)
                    scaler.update()
                    sched.step()
                    opt.zero_grad(set_to_none=True)
            validate(stage, total / max(n, 1), time.time() - e0, lrs)
            epoch += 1
            if stopper.should_stop:
                log.info("seed %d stage %d: early stop (best epoch %d)", seed, stage, stopper.best_epoch)
                break

    model.load_state_dict(torch.load(ckpt, map_location=device, weights_only=True))
    res = {s: predict(model, loaders[s], device, True, args.max_batches) for s in ("val", "test")}
    pd.concat([frame(res[s], classes, s, seed) for s in ("val", "test")], ignore_index=True).to_csv(
        out_dir / "predictions.csv", index=False)
    best_stage = next(h["stage"] for h in history if h["epoch"] == stopper.best_epoch)
    summary = {"seed": seed, "best_epoch": stopper.best_epoch, "best_stage": best_stage,
               "best_val_macro_f1": stopper.best, "probe_val_macro_f1": history[0]["val_macro_f1"],
               "epochs_run": epoch, "train_minutes": (time.time() - t0) / 60, "test_macro_f1": macro_f1(res["test"])}
    del model, loaders
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return summary


# -------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--pad-mode", choices=["constant", "reflect"], default="constant")
    ap.add_argument("--head-epochs", type=int, default=3, help="stage 1: encoder frozen, head only")
    ap.add_argument("--epochs", type=int, default=10, help="stage 2: top blocks + head")
    ap.add_argument("--top-blocks", type=int, default=4, help="blocks trained in stage 2 (12 = the whole encoder)")
    ap.add_argument("--patience", type=int, default=10, help="epochs without a better validation macro-F1, per stage "
                    "(10 = stage 2 always runs to the end: validation first dips when the encoder starts to move)")
    ap.add_argument("--lr", type=float, default=1e-5, help="learning rate of the top block")
    ap.add_argument("--head-lr", type=float, default=1e-4)
    ap.add_argument("--layer-decay", type=float, default=0.75)
    ap.add_argument("--weight-decay", type=float, default=0.05)
    ap.add_argument("--drop-path", type=float, default=0.0)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--batch-size", type=int, default=8, help="518 px ViT-B: 8 fits a 12 GB GPU without checkpointing")
    ap.add_argument("--accum", type=int, default=4, help="batches per optimizer step (8 x 4 = 32 cases)")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "finetune_dinov2")
    ap.add_argument("--skip-existing", action="store_true", help="reuse seeds that already have results")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = copy.deepcopy(load_config(args.config))
    cfg["data"]["image_size"] = timm.get_pretrained_cfg(MODEL).input_size[-1]
    cfg["data"]["pad_mode"] = args.pad_mode
    cfg["normalize"] = {"mean": list(timm.get_pretrained_cfg(MODEL).mean), "std": list(timm.get_pretrained_cfg(MODEL).std)}
    cfg["loader"].update(batch_size=args.batch_size, num_workers=args.num_workers)
    root = args.out_root / args.pad_mode
    (root / "seed_checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "run_options.json").write_text(json.dumps({k: str(v) for k, v in vars(args).items()}, indent=2),
                                           encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    flats = []
    for seed in args.seeds:
        out_dir, ckpt = root / f"seed{seed}", root / "seed_checkpoints" / f"ft_seed{seed}.pt"
        out_dir.mkdir(exist_ok=True)
        if args.skip_existing and (out_dir / "metrics_summary.csv").exists() and ckpt.exists():
            log.info("seed %d already done, skipped", seed)
        else:
            ckpt.unlink(missing_ok=True)
            write_seed_runs(root / "seed_runs.csv", [train_seed(seed, cfg, args, out_dir, ckpt, device)])
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", str(args.n_boot)])
        flats.append(pd.read_csv(out_dir / "metrics_summary.csv", dtype={"seed": str}))

    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    summary.insert(0, "experiment", "T4.7_finetune_dinov2")
    summary.insert(1, "pad_mode", args.pad_mode)
    summary.to_csv(root / "finetune_test.csv", index=False)
    for _, r in summary[(summary["scope"] == "overall") & summary["metric"].isin(["macro_f1", "balanced_acc"])].iterrows():
        log.info("test %-12s %s (n_seeds=%d)", r["metric"], r["mean_pm_sd"], r["n_seeds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
