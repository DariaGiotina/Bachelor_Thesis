"""E1 arm 3 (and E2): photo + questionnaire fusion over split seeds 0-4.

Same protocol as ``run_image_only.py`` (same cases, splits, backbone, staged fine-tuning through
``fit_staged``, imbalance correction, early stopping on validation macro-F1, one test with the best
checkpoint, evaluate.py, mean +- sd over seeds), with ``LateFusionNet`` instead of the image-only model.

Training hides answers at random (modality dropout): the whole questionnaire with
``p_modality_drop`` and single answers with ``p_field_drop`` (``configs/base.yaml``, ``train`` block).
``--q_dropout`` picks the training mode (``dropout_utils.py``): ``fixed`` (default, the rates above),
``none`` (no hidden answers, the "without dropout" arm of E2; ``--no-dropout`` is the old spelling) or
``random`` (a field-drop rate drawn from 0-100% for every batch, plus the whole questionnaire hidden
with ``answer_dropout.p_full``; Task 3.4). The test split is scored with a
share r of the answers hidden for every r in ``train.eval_missing_rates``, with the same hidden
answers as ``run_q_only.py`` (same generator use, batch size and order).

Outputs in ``runs/e1_fusion/<backbone>_<variant>_<balance>[_nodrop|_randdrop]/`` (git-ignored):
  seed_checkpoints/fusion_late_<variant>_seed{seed}.pt   best-validation weights (state_dict);
                   fusion_dropout_<variant>_seed{seed}.pt for --q_dropout random
  seed{seed}/log.csv, predictions.csv, metrics_summary.* per seed
  seed_runs.csv, e1_fusion_test.csv                       across-seed summary, per missing rate

Usage::

    python run_fusion.py                                    # concat, config backbone, seeds 0-4
    python run_fusion.py --fusion gated --balance sampler
    python run_fusion.py --q_dropout none                   # E2: trained without hidden answers
    python run_fusion.py --q_dropout random --seeds 0 1 2 3 4 5 6 7 8 9   # E2: per-batch sampled rate
    python run_fusion.py --epochs 1 --max-batches 3 --seeds 0 --n-boot 50 --num-workers 0   # smoke test
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from engine import evaluate  # noqa: E402
from models.fusion_model import FUSIONS  # noqa: E402
from run_image_only import (BACKBONES, BALANCES, aggregate_seeds, build_balanced_training, fit_staged,  # noqa: E402
                            write_seed_runs)
from dropout_utils import MODES, make_dropout_adapt, training_rates  # noqa: E402
from train import build_fusion, field_index, make_fusion_adapt, predictions_frame  # noqa: E402

SUFFIX = {"none": "_nodrop", "fixed": "", "random": "_randdrop"}
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_fusion")


def train_seed(seed: int, cfg: dict, opts: dict, out_dir: Path, ckpt: Path, device: torch.device) -> dict:
    seed_everything(seed)
    tc = cfg["train"]
    loaders = get_dataloaders(cfg, seed, only_available=opts["only_available"])
    loss_fn, loaders = build_balanced_training(opts["balance"], cfg, seed, loaders, device, opts["only_available"])
    train_ds = loaders["train"].dataset
    classes, fields = train_ds.classes, field_index(train_ds.q_cols, train_ds.m_cols)
    model = build_fusion(cfg, len(classes), len(train_ds.q_cols), len(train_ds.m_cols)).to(device)
    adapt = make_dropout_adapt(fields, opts["drop_rates"], seed=seed)
    log.info("seed %d | %s %s %s | train=%d val=%d test=%d | answer dropout: %s", seed,
             cfg["image_baseline"]["backbone"], cfg["fusion"]["variant"], opts["balance"], len(train_ds),
             len(loaders["val"].dataset), len(loaders["test"].dataset), opts["drop_rates"])
    fit = fit_staged(model, loaders, loss_fn, adapt, cfg, ckpt, out_dir, device, seed, opts["epochs"],
                     opts["max_batches"])

    model.load_state_dict(torch.load(ckpt, map_location=device))  # test once, best-validation weights
    frames, test = [], {}
    for split, rates in (("val", [0.0]), ("test", tc["eval_missing_rates"])):
        for rate in rates:
            ev = make_fusion_adapt(fields, 0.0, 0.0, rate, seed)  # fresh generator per rate
            res = evaluate(model, loaders[split], loss_fn, device, ev, tc["amp"], opts["max_batches"])
            frames.append(predictions_frame(res, classes, split, seed, rate))
            if split == "test":
                test[f"test_macro_f1_missing_{rate}"] = res["macro_f1"]
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    del model, loaders
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return {"seed": seed, **fit, **test}


def run(options: dict | None = None) -> pd.DataFrame:
    defaults = {"config": ROOT / "configs" / "base.yaml", "backbone": None, "fusion": None,
                "balance": "weighted_loss", "seeds": [0, 1, 2, 3, 4], "out_root": ROOT / "runs" / "e1_fusion",
                "epochs": None, "max_batches": None, "num_workers": None, "n_boot": None, "only_available": False,
                "no_dropout": False, "q_dropout": None, "skip_existing": False}
    opts = {**defaults, **(options or {})}
    mode = opts["q_dropout"] or ("none" if opts["no_dropout"] else "fixed")
    if opts["no_dropout"] and mode != "none":
        raise ValueError("--no-dropout conflicts with --q_dropout " + mode)
    opts["q_dropout"] = mode
    if opts["balance"] not in BALANCES:
        raise ValueError(f"balance must be one of {BALANCES}, got {opts['balance']!r}")
    cfg = copy.deepcopy(load_config(opts["config"]))
    if opts["backbone"]:
        cfg["image_baseline"]["backbone"] = opts["backbone"]
    if opts["fusion"]:
        cfg["fusion"]["variant"] = opts["fusion"]
    if opts["num_workers"] is not None:
        cfg["loader"]["num_workers"] = opts["num_workers"]
    tc = cfg["train"]
    opts["drop_rates"] = training_rates(mode, cfg)
    variant, n_boot = cfg["fusion"]["variant"], opts["n_boot"] or tc.get("n_boot", 1000)
    exp = f"{cfg['image_baseline']['backbone']}_{variant}_{opts['balance']}" + SUFFIX[mode]
    ckpt_name = "fusion_dropout" if mode == "random" else "fusion_late"
    root = Path(opts["out_root"]) / exp
    (root / "seed_checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("E1 fusion | %s | seeds %s | device %s | out %s", exp, opts["seeds"], device, root)

    runs, flats = [], []
    for seed in opts["seeds"]:
        out_dir, ckpt = root / f"seed{seed}", root / "seed_checkpoints" / f"{ckpt_name}_{variant}_seed{seed}.pt"
        out_dir.mkdir(exist_ok=True)
        if opts["skip_existing"] and ckpt.exists() and (out_dir / "metrics_summary.csv").exists():
            log.info("seed %d already done, skipped (--skip-existing)", seed)
        else:
            ckpt.unlink(missing_ok=True)  # never resume from another run's weights
            runs.append({"backbone": cfg["image_baseline"]["backbone"], "fusion": variant, "balance": opts["balance"],
                         "q_dropout": mode, "p_full": opts["drop_rates"]["p_full"],
                         "p_field": opts["drop_rates"].get("p_field", "U(%g,%g)" % (
                             opts["drop_rates"].get("p_field_low", 0), opts["drop_rates"].get("p_field_high", 1))),
                         **train_seed(seed, cfg, opts, out_dir, ckpt, device)})
            write_seed_runs(root / "seed_runs.csv", runs[-1:])
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", str(n_boot)])
        flats.append(pd.read_csv(out_dir / "metrics_summary.csv", dtype={"seed": str}))

    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    for i, (k, v) in enumerate((("experiment", "E1_fusion"), ("backbone", cfg["image_baseline"]["backbone"]),
                                ("fusion", variant), ("balance", opts["balance"]),
                                ("modality_dropout", mode != "none"), ("q_dropout", mode))):
        summary.insert(i, k, v)
    summary.to_csv(root / "e1_fusion_test.csv", index=False)
    (root / "run_options.json").write_text(json.dumps({k: str(v) for k, v in opts.items()}, indent=2),
                                           encoding="utf-8")
    head = summary[(summary["scope"] == "overall") & (summary["metric"] == "macro_f1")]
    for _, r in head.iterrows():
        log.info("test macro-F1, %3.0f%% of answers hidden: %s (n_seeds=%d)", 100 * r["missing_pct"],
                 r["mean_pm_sd"], r["n_seeds"])
    log.info("wrote %s", root / "e1_fusion_test.csv")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--backbone", choices=BACKBONES, default=None, help="default: image_baseline.backbone")
    ap.add_argument("--fusion", choices=FUSIONS, default=None, help="default: fusion.variant")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "e1_fusion")
    ap.add_argument("--no-dropout", action="store_true", help="same as --q_dropout none (E2 control arm)")
    ap.add_argument("--q_dropout", "--q-dropout", choices=MODES, default=None,
                    help="answer dropout in training: none | fixed (default) | random (rate sampled per batch)")
    ap.add_argument("--epochs", type=int, default=None, help="epochs per stage (default: config)")
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=None)
    ap.add_argument("--only-available", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(vars(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
