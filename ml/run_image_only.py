"""E1 arm 1: image-only baseline over split seeds 0-4, with a class-imbalance ablation.

For every seed the script loads that seed's split variant (``splits/train_val_test_splits.json``),
builds ``SkinImageBaseline`` (EfficientNet-B0 or MobileNetV3) and runs the staged fine-tuning of
``configs/base.yaml`` (stage 1 head only -> stage 2 top blocks -> stage 3 all layers) with the
epoch functions of ``engine.py`` and early stopping on validation macro-F1. The best checkpoint is
tested once; the test predictions go through ``evaluate.py`` and the five seeds are summarised as
mean +- standard deviation.

Imbalance ablation (``--balance``), exactly one correction at a time:
  weighted_loss  class-weighted cross-entropy (inverse class frequency, ``losses.class_weights``);
                 the train loader shuffles uniformly.
  sampler        unweighted cross-entropy; the train loader draws cases with a
                 ``WeightedRandomSampler`` (probability proportional to 1 / class count, with
                 replacement), so every class is seen about equally often per epoch.

A case the sampler draws several times in one epoch gets a different image/augmentation each time
(the dataset's random draw depends on (seed, epoch, case, repeat)); otherwise the copies of a rare
case would be identical.

Outputs in ``runs/e1_image_only/<backbone>_<balance>/`` (git-ignored):
  seed_checkpoints/img_only_seed{seed}.pt   best-validation weights (state_dict)
  seed{seed}/log.csv, predictions.csv      training log; val + test predictions (evaluate.py format)
  seed{seed}/metrics_summary.*, risk_coverage.csv   evaluate.py on the test split
  seed_runs.csv                            best epoch / stage / val macro-F1 / time per seed
  e1_image_only_test.csv                   test metrics across seeds: mean, sd, min, max, "mean +- sd"

Usage::

    python run_image_only.py --backbone efficientnet_b0 --balance weighted_loss
    python run_image_only.py --backbone mobilenetv3_large_100 --balance sampler --seeds 0 1 2 3 4
    python run_image_only.py --epochs 1 --max-batches 3 --seeds 0 1 --n-boot 50 --num-workers 0   # smoke test

From a notebook: ``run({"backbone": "efficientnet_b0", "balance": "sampler"})``.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, WeightedRandomSampler

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, SCINDataset, get_dataloaders, load_config  # noqa: E402
from engine import EarlyStopping, evaluate, image_only_adapt, timed, train_one_epoch  # noqa: E402
from losses import class_weights  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from train import param_groups, predictions_frame, stage_plan  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_image_only")
BALANCES = ("weighted_loss", "sampler")
BACKBONES = ("efficientnet_b0", "mobilenetv3_large_100")
DEFAULTS = {"config": ROOT / "configs" / "base.yaml", "backbone": "efficientnet_b0", "balance": "weighted_loss",
            "seeds": [0, 1, 2, 3, 4], "out_root": ROOT / "runs" / "e1_image_only", "epochs": None,
            "max_batches": None, "num_workers": None, "n_boot": None, "only_available": False,
            "skip_existing": False}


# ----------------------------------------------------------------------------- imbalance ablation
class RepeatAwareSCINDataset(SCINDataset):
    """Train split whose index may carry a repeat number: index = case + n_cases * repeat.

    Repeat 0 is exactly the item of ``SCINDataset`` (same image and augmentation draw); repeat k > 0
    seeds its own draw, so a case drawn k + 1 times in one epoch gives k + 1 different views.
    """

    def __getitem__(self, index: int) -> dict:
        n = len(self.case_ids)
        idx, repeat = index % n, index // n
        if repeat == 0:
            return super().__getitem__(idx)
        item = super().__getitem__(idx)  # labels, questionnaire and ids of the case; the view is redrawn below
        rng = np.random.default_rng([self.seed, self.epoch, idx, repeat])
        img, ok = self._load_image(idx, rng)
        self.transform.set_random_seed(int(rng.integers(2**31 - 1)))
        item["image"], item["image_ok"] = self.transform(image=img)["image"], torch.tensor(int(ok))
        return item


class RepeatNumberingSampler(WeightedRandomSampler):
    """``WeightedRandomSampler`` that numbers repeated draws within an epoch (see above)."""

    def __iter__(self):
        n, seen = len(self.weights), Counter()
        for i in super().__iter__():
            yield i + n * seen[i]
            seen[i] += 1


def sample_weights(labels: np.ndarray, n_classes: int) -> torch.Tensor:
    """Per-case draw weight 1 / (count of its class): each class has the same expected share."""
    counts = np.bincount(labels, minlength=n_classes).astype(np.float64)
    return torch.as_tensor(1.0 / counts[labels], dtype=torch.double)


def build_balanced_training(balance: str, cfg: dict, seed: int, loaders: dict, device: torch.device,
                            only_available: bool) -> tuple[nn.Module, dict]:
    """Loss and loaders for one ablation arm (the other arm's correction is never applied too)."""
    train_ds = loaders["train"].dataset
    n_classes = len(train_ds.classes)
    if balance == "weighted_loss":
        return nn.CrossEntropyLoss(weight=class_weights(train_ds.labels, n_classes).to(device)), loaders
    if balance != "sampler":
        raise ValueError(f"balance must be one of {BALANCES}, got {balance!r}")
    ds = RepeatAwareSCINDataset(cfg, "train", seed, only_available)
    lc, nw = cfg["loader"], cfg["loader"]["num_workers"]
    sampler = RepeatNumberingSampler(sample_weights(ds.labels, n_classes), num_samples=len(ds), replacement=True,
                                     generator=torch.Generator().manual_seed(seed))
    train_loader = DataLoader(ds, batch_size=lc["batch_size"], sampler=sampler, num_workers=nw,
                              pin_memory=lc["pin_memory"] and torch.cuda.is_available(),
                              persistent_workers=lc["persistent_workers"] and nw > 0, drop_last=False)
    return nn.CrossEntropyLoss(), {**loaders, "train": train_loader}


# ------------------------------------------------------------------------------- staged training
def fit_staged(model: nn.Module, loaders: dict, loss_fn: nn.Module, adapt, cfg: dict, ckpt: Path, out_dir: Path,
               device: torch.device, seed: int, epochs: int | None = None, max_batches: int | None = None) -> dict:
    """Staged fine-tuning (``image_baseline`` stages of the config) with early stopping on val macro-F1.

    Shared by every model with ``set_stage`` (image-only and fusion), so all arms of E1 train the same
    way. Each stage starts from the best checkpoint so far and has its own patience; the best weights
    are in ``ckpt`` and the epoch log in ``out_dir/log.csv``. Returns the training summary.
    """
    tc = cfg["train"]
    scaler = torch.amp.GradScaler(enabled=tc["amp"] and device.type == "cuda")
    stopper, history, epoch, best_stage, t0 = EarlyStopping(tc["early_stopping_patience"]), [], 0, None, time.time()
    for phase in stage_plan(model, cfg, epochs):
        if ckpt.exists() and stopper.best_epoch >= 0:
            model.load_state_dict(torch.load(ckpt, map_location=device))  # each stage starts from the best so far
        opt = torch.optim.AdamW(param_groups(model, phase, cfg))
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=phase["epochs"])
        stopper.bad_epochs = 0  # own patience per stage
        log.info("seed %d stage %d: %d trainable parameters, head lr %.1e", seed, phase["stage"],
                 model.n_trainable(), phase["lr"])
        for _ in range(phase["epochs"]):
            loaders["train"].dataset.set_epoch(epoch)
            train_loss, secs = timed(train_one_epoch, model, loaders["train"], loss_fn, opt, scaler, device,
                                     adapt, tc["amp"], tc["grad_clip"], max_batches)
            val = evaluate(model, loaders["val"], loss_fn, device, adapt, tc["amp"], max_batches)
            lr = max(g["lr"] for g in opt.param_groups)
            sched.step()
            history.append({"epoch": epoch, "stage": phase["stage"], "train_loss": train_loss,
                            "val_loss": val["loss"], "val_macro_f1": val["macro_f1"],
                            "val_balanced_acc": val["balanced_acc"], "epoch_time": round(secs, 1), "lr": lr})
            pd.DataFrame(history).to_csv(out_dir / "log.csv", index=False)
            if stopper.step(val["macro_f1"], epoch):
                torch.save(model.state_dict(), ckpt)
                best_stage = phase["stage"]
            log.info("seed %d epoch %d train %.4f val %.4f macro-F1 %.3f%s (%.0fs)", seed, epoch, train_loss,
                     val["loss"], val["macro_f1"], " *" if stopper.best_epoch == epoch else "", secs)
            epoch += 1
            if stopper.should_stop:
                log.info("seed %d stage %d: early stop (best epoch %d)", seed, phase["stage"], stopper.best_epoch)
                break
    return {"best_epoch": stopper.best_epoch, "best_stage": best_stage, "best_val_macro_f1": stopper.best,
            "epochs_run": epoch, "train_minutes": (time.time() - t0) / 60}


# --------------------------------------------------------------------------------------- one seed
def train_seed(seed: int, cfg: dict, opts: dict, out_dir: Path, ckpt: Path, device: torch.device) -> dict:
    """Staged fine-tuning on one split seed; returns the training summary (best checkpoint in ``ckpt``)."""
    seed_everything(seed)
    tc, ib = cfg["train"], cfg["image_baseline"]
    loaders = get_dataloaders(cfg, seed, only_available=opts["only_available"])
    loss_fn, loaders = build_balanced_training(opts["balance"], cfg, seed, loaders, device, opts["only_available"])
    train_ds, classes = loaders["train"].dataset, loaders["train"].dataset.classes
    log.info("seed %d | %s %s | train=%d val=%d test=%d | class counts %s", seed, opts["backbone"], opts["balance"],
             len(train_ds), len(loaders["val"].dataset), len(loaders["test"].dataset),
             dict(zip(classes, np.bincount(train_ds.labels, minlength=len(classes)).tolist())))

    model = SkinImageBaseline(len(classes), ib["backbone"], tc["pretrained"], ib["top_blocks"],
                              ib["drop_rate"]).to(device)
    fit = fit_staged(model, loaders, loss_fn, image_only_adapt, cfg, ckpt, out_dir, device, seed,
                     opts["epochs"], opts["max_batches"])

    # Test once, with the best-validation weights.
    model.load_state_dict(torch.load(ckpt, map_location=device))
    frames = []
    for split in ("val", "test"):
        res = evaluate(model, loaders[split], loss_fn, device, image_only_adapt, tc["amp"], opts["max_batches"])
        frames.append(predictions_frame(res, classes, split, seed, 0.0))
        if split == "test":
            test = res
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    summary = {"seed": seed, **fit, "test_macro_f1": test["macro_f1"], "test_balanced_acc": test["balanced_acc"],
               "n_test": test["n"], "n_test_image_failed": test["n_image_failed"]}
    del model, loaders
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return summary


# ------------------------------------------------------------------------------------ aggregation
def aggregate_seeds(flat: pd.DataFrame) -> pd.DataFrame:
    """Test metrics across seeds (mean, sd, min, max) from the stacked evaluate.py metrics_summary.csv,
    separately for every missing-answer rate (``missing_pct``).

    The worst tone group can differ between seeds, so its rows are pooled under group 'worst' (and
    'best-worst gap') with the per-seed group names listed in ``worst_groups``.
    """
    df = flat[flat["split"] == "test"].copy()
    worst = df["group"].str.startswith("worst=")
    df["seed_group"] = df["group"]
    df.loc[worst, "group"] = "worst"
    df.loc[df["metric"] == "gap_macro_f1", "group"] = "best-worst gap"
    keys = ["missing_pct", "scope", "group", "metric"]
    agg = df.groupby(keys, sort=False).agg(
        n_seeds=("value", "count"), mean=("value", "mean"), sd=("value", "std"), min=("value", "min"),
        max=("value", "max"), mean_n_cases=("n_cases", "mean")).reset_index()
    named = df[worst].groupby(keys)["seed_group"].agg(
        lambda s: "; ".join(f"{g.removeprefix('worst=')} x{n}" for g, n in Counter(s).most_common()))
    agg = agg.merge(named.rename("worst_groups").reset_index(), on=keys, how="left")
    agg["mean_pm_sd"] = [f"{m:.3f} ± {s:.3f}" if pd.notna(s) else f"{m:.3f}" for m, s in zip(agg["mean"], agg["sd"])]
    return agg


# ------------------------------------------------------------------------------------------- main
def run(options: dict | None = None) -> pd.DataFrame:
    """Train and test every seed; returns the across-seed summary (also written to CSV)."""
    opts = {**DEFAULTS, **(options or {})}
    if opts["balance"] not in BALANCES:
        raise ValueError(f"balance must be one of {BALANCES}, got {opts['balance']!r}")
    cfg = copy.deepcopy(load_config(opts["config"]))
    cfg["image_baseline"]["backbone"] = opts["backbone"]
    if opts["num_workers"] is not None:
        cfg["loader"]["num_workers"] = opts["num_workers"]
    n_boot = opts["n_boot"] or cfg["train"].get("n_boot", 1000)
    exp = f"{opts['backbone']}_{opts['balance']}"
    root = Path(opts["out_root"]) / exp
    (root / "seed_checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("E1 image-only | %s | seeds %s | device %s | out %s", exp, opts["seeds"], device, root)

    runs, flats = [], []
    for seed in opts["seeds"]:
        out_dir, ckpt = root / f"seed{seed}", root / "seed_checkpoints" / f"img_only_seed{seed}.pt"
        out_dir.mkdir(exist_ok=True)
        done = (out_dir / "metrics_summary.csv").exists() and ckpt.exists()
        if opts["skip_existing"] and done:
            log.info("seed %d already done, skipped (--skip-existing)", seed)
        else:
            ckpt.unlink(missing_ok=True)  # never resume from another run's weights
            runs.append({"backbone": opts["backbone"], "balance": opts["balance"],
                         **train_seed(seed, cfg, opts, out_dir, ckpt, device)})
            pd.DataFrame(runs).to_csv(root / "seed_runs.csv", index=False)
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", str(n_boot)])
        flats.append(pd.read_csv(out_dir / "metrics_summary.csv", dtype={"seed": str}))

    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    summary.insert(0, "experiment", "E1_image_only")
    summary.insert(1, "backbone", opts["backbone"])
    summary.insert(2, "balance", opts["balance"])
    summary.to_csv(root / "e1_image_only_test.csv", index=False)
    (root / "run_options.json").write_text(json.dumps({k: str(v) for k, v in opts.items()}, indent=2),
                                           encoding="utf-8")
    head = summary[(summary["scope"] == "overall") & summary["metric"].isin(["macro_f1", "balanced_acc", "ece"])]
    for _, r in head.iterrows():
        log.info("test %-12s %s (n_seeds=%d)", r["metric"], r["mean_pm_sd"], r["n_seeds"])
    log.info("wrote %s", root / "e1_image_only_test.csv")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=DEFAULTS["config"])
    ap.add_argument("--backbone", choices=BACKBONES, default=DEFAULTS["backbone"])
    ap.add_argument("--balance", choices=BALANCES, default=DEFAULTS["balance"],
                    help="class-imbalance correction: weighted cross-entropy or WeightedRandomSampler")
    ap.add_argument("--seeds", type=int, nargs="+", default=DEFAULTS["seeds"])
    ap.add_argument("--out-root", type=Path, default=DEFAULTS["out_root"])
    ap.add_argument("--epochs", type=int, default=None, help="epochs per stage (default: config)")
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=None, help="bootstrap resamples for evaluate.py")
    ap.add_argument("--only-available", action="store_true", help="skip cases whose images are missing")
    ap.add_argument("--skip-existing", action="store_true", help="reuse seeds that already have results")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(vars(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
