"""Train and evaluate a skin-concern classifier on one split seed.

Loads ``configs/base.yaml``, builds the DataLoaders, a model, the loss (class-weighted
cross-entropy or focal), and runs the epoch loop of ``engine.py`` with early stopping on validation
macro-F1. Writes to ``runs/<exp_name>/``: ``best_model.pt``, ``log.csv`` (train_loss, val_loss,
val_macro_f1, epoch_time, ...), ``results.json`` (training summary), ``predictions.csv`` (best model
on validation and on test at every missing-answer rate) and, through ``evaluate.py``,
``metrics_summary.json`` / ``.csv`` and ``risk_coverage.csv``.

Models (``--model``):
  dummy       tiny CNN, image only (placeholder to test the pipeline)
  image_only  timm EfficientNet-B0 or MobileNetV3 (``--backbone``), image only, trained in stages
              (head only -> top blocks -> all layers; see ``image_baseline`` in the config)
  fusion      EfficientNet-B0 + questionnaire branch; questionnaire input is q_vec + q_mask and
              answers are hidden at random during training (modality dropout, never imputed)

Missing-answer evaluation: the fusion model is tested with a share r of the questionnaire fields
hidden (each field independently, on top of the answers that are naturally missing), for every r
in ``train.eval_missing_rates``; r = 1 hides the whole questionnaire.

Usage::

    python train.py --model dummy --epochs 3
    python train.py --model image_only --backbone mobilenetv3_large_100 --seed 0
    python train.py --model fusion --seed 0 --loss-type focal
    python train.py --model dummy --epochs 2 --max-batches 5 --only-available --num-workers 0
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from engine import EarlyStopping, evaluate, image_only_adapt, timed, train_one_epoch  # noqa: E402
from losses import build_loss  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from skinconcern.model import FusionClassifier  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("train")


# ------------------------------------------------------------------ missing-answer simulation
def field_index(q_cols: list[str], m_cols: list[str]) -> list[torch.Tensor]:
    """For each mask column m__<field>, the indices of its feature columns f__<field>__*."""
    out = []
    for m in m_cols:
        field = m.split("__", 1)[1]
        out.append(torch.tensor([i for i, c in enumerate(q_cols) if c.split("__")[1] == field]))
    return out


def hide_answers(q_vec, q_mask, fields, p_modality: float, p_field: float, gen: torch.Generator | None = None):
    """Simulate missing answers: zero the features and set the mask to 1 (never imputes)."""
    q_vec, q_mask = q_vec.clone(), q_mask.clone()
    n = q_vec.size(0)
    whole = torch.rand(n, generator=gen) < p_modality
    for j, cols in enumerate(fields):
        drop = whole | (torch.rand(n, generator=gen) < p_field)
        q_vec[drop.nonzero().squeeze(1).unsqueeze(1), cols.unsqueeze(0)] = 0.0
        q_mask[drop, j] = 1.0
    return q_vec, q_mask


def make_fusion_adapt(fields, p_modality_train: float, p_field_train: float,
                      p_field_eval: float = 0.0, seed: int = 0):
    """Batch -> model kwargs for the fusion model.

    Training: whole questionnaire hidden with p_modality_train, single fields with p_field_train.
    Evaluation: each field hidden with p_field_eval (fixed generator, so every model sees the same
    hidden answers).
    """
    gen = torch.Generator().manual_seed(seed)

    def adapt(batch: dict, training: bool) -> dict:
        pm, pf = (p_modality_train, p_field_train) if training else (0.0, p_field_eval)
        q_vec, q_mask = batch["q_vec"], batch["q_mask"]
        if pm > 0 or pf > 0:
            q_vec, q_mask = hide_answers(q_vec, q_mask, fields, pm, pf, gen)
        return {"image": batch["image"], "q_vec": q_vec, "q_mask": q_mask}

    return adapt


# --------------------------------------------------------------------------------------- models
class DummyCNN(nn.Module):
    """Placeholder image classifier (3 conv blocks + linear head), only for pipeline checks."""

    def __init__(self, n_classes: int):
        super().__init__()
        blocks, c = [], 3
        for out in (16, 32, 64):
            blocks += [nn.Conv2d(c, out, 3, stride=2, padding=1), nn.BatchNorm2d(out), nn.ReLU()]
            c = out
        self.net = nn.Sequential(*blocks, nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(c, n_classes))

    def forward(self, image):
        return self.net(image)


def build_model(name: str, cfg: dict, n_classes: int, n_q_features: int, n_q_fields: int) -> nn.Module:
    tc, ib = cfg["train"], cfg["image_baseline"]
    if name == "dummy":
        return DummyCNN(n_classes)
    if name == "image_only":
        return SkinImageBaseline(n_classes, ib["backbone"], tc["pretrained"], ib["top_blocks"], ib["drop_rate"])
    if name == "fusion":
        return FusionClassifier(n_classes, n_q_features, n_q_fields, tc["backbone"], tc["pretrained"],
                                tc["q_hidden"], use_questionnaire=True)
    raise ValueError(f"unknown model {name!r}")


def stage_plan(model: nn.Module, cfg: dict, epochs_override: int | None) -> list[dict]:
    """Training phases: the fine-tuning stages for staged models, else one phase."""
    tc = cfg["train"]
    if not hasattr(model, "set_stage"):
        return [{"stage": None, "epochs": epochs_override or tc["epochs"], "lr": tc["lr"]}]
    ib = cfg["image_baseline"]
    return [{"stage": s, "epochs": epochs_override or ib["stages"][s]["epochs"], "lr": ib["stages"][s]["lr"]}
            for s in ib["run_stages"]]


def param_groups(model: nn.Module, phase: dict, cfg: dict) -> list[dict]:
    wd = cfg["train"]["weight_decay"]
    if phase["stage"] is not None:
        model.set_stage(phase["stage"])
        return model.get_optimizer_param_groups(phase["lr"], cfg["image_baseline"]["backbone_lr_mult"], wd)
    return [{"params": [p for p in model.parameters() if p.requires_grad], "lr": phase["lr"],
             "weight_decay": wd, "name": "all"}]


# -------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--model", choices=["dummy", "image_only", "fusion"], default="dummy")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--exp-name", default=None, help="run folder name (default: <model>[_<backbone>]_seed<seed>)")
    ap.add_argument("--epochs", type=int, default=None, help="epochs (per stage for staged models)")
    ap.add_argument("--backbone", default=None, help="image_only backbone, e.g. mobilenetv3_large_100")
    ap.add_argument("--stages", default=None, help="image_only stages to run, e.g. 1,2 (default: config)")
    ap.add_argument("--loss-type", choices=["weighted_ce", "focal"], default=None)
    ap.add_argument("--patience", type=int, default=None)
    ap.add_argument("--p-modality-drop", type=float, default=None)
    ap.add_argument("--p-field-drop", type=float, default=None)
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--only-available", action="store_true", help="skip cases whose images are missing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config(args.config)
    tc = cfg["train"]
    patience = args.patience or tc["early_stopping_patience"]
    loss_type = args.loss_type or tc["loss_type"]
    p_mod = tc["p_modality_drop"] if args.p_modality_drop is None else args.p_modality_drop
    p_fld = tc["p_field_drop"] if args.p_field_drop is None else args.p_field_drop
    if args.num_workers is not None:
        cfg["loader"]["num_workers"] = args.num_workers
    if args.backbone:
        cfg["image_baseline"]["backbone"] = args.backbone
    if args.stages:
        cfg["image_baseline"]["run_stages"] = [int(s) for s in args.stages.split(",")]
    tag = f"_{cfg['image_baseline']['backbone']}" if args.model == "image_only" else ""
    exp = args.exp_name or f"{args.model}{tag}_seed{args.seed}"
    out_dir = ROOT / "runs" / exp
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    (out_dir / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")  # for reproducibility
    loaders = get_dataloaders(cfg, args.seed, only_available=args.only_available)
    train_ds = loaders["train"].dataset
    fields = field_index(train_ds.q_cols, train_ds.m_cols)
    n_classes = len(train_ds.classes)

    model = build_model(args.model, cfg, n_classes, len(train_ds.q_cols), len(train_ds.m_cols)).to(device)
    loss_fn = build_loss(loss_type, train_ds.labels, n_classes, device, tc["focal_gamma"])
    plan = stage_plan(model, cfg, args.epochs)
    scaler = torch.amp.GradScaler(enabled=tc["amp"] and device.type == "cuda")
    adapt = make_fusion_adapt(fields, p_mod, p_fld, seed=args.seed) if args.model == "fusion" else image_only_adapt
    log.info("%s | device=%s loss=%s classes=%s train=%d val=%d test=%d", exp, device, loss_type,
             train_ds.classes, len(train_ds), len(loaders["val"].dataset), len(loaders["test"].dataset))

    stopper, history, epoch, best_stage = EarlyStopping(patience), [], 0, None
    best_path = out_dir / "best_model.pt"
    best_path.unlink(missing_ok=True)  # a rerun in the same folder must not start from the old run's weights
    for phase in plan:
        if phase["stage"] is not None and best_path.exists():
            model.load_state_dict(torch.load(best_path, map_location=device))  # continue from the best so far
        opt = torch.optim.AdamW(param_groups(model, phase, cfg))
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=phase["epochs"])
        stopper.bad_epochs = 0  # each stage gets its own patience
        n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
        if phase["stage"] is not None:
            log.info("stage %d: %d trainable parameters, head lr %.1e", phase["stage"], n_train, phase["lr"])
        for _ in range(phase["epochs"]):
            train_ds.set_epoch(epoch)
            train_loss, secs = timed(train_one_epoch, model, loaders["train"], loss_fn, opt, scaler, device, adapt,
                                     tc["amp"], tc["grad_clip"], args.max_batches)
            val = evaluate(model, loaders["val"], loss_fn, device, adapt, tc["amp"], args.max_batches)
            lrs = {g.get("name", str(i)): g["lr"] for i, g in enumerate(opt.param_groups)}  # before the step
            sched.step()
            row = {"epoch": epoch, "stage": phase["stage"], "train_loss": train_loss, "val_loss": val["loss"],
                   "val_macro_f1": val["macro_f1"], "val_balanced_acc": val["balanced_acc"],
                   "epoch_time": round(secs, 1), "lr": max(lrs.values()),
                   "lr_backbone": min((v for k, v in lrs.items() if k.startswith("backbone")), default=None),
                   "n_trainable": n_train}
            history.append(row)
            pd.DataFrame(history).to_csv(out_dir / "log.csv", index=False)
            if stopper.step(val["macro_f1"], epoch):
                torch.save(model.state_dict(), best_path)
                best_stage = phase["stage"]
            log.info("epoch %d train %.4f val %.4f macro-F1 %.3f%s (%.0fs)", epoch, train_loss, val["loss"],
                     val["macro_f1"], " *" if stopper.best_epoch == epoch else "", secs)
            epoch += 1
            if stopper.should_stop:
                log.info("early stopping: no macro-F1 gain for %d epochs (best epoch %d)", patience,
                         stopper.best_epoch)
                break

    # One final test evaluation with the best-validation weights.
    model.load_state_dict(torch.load(out_dir / "best_model.pt", map_location=device))
    results = {"run": exp, "model": args.model, "seed": args.seed, "loss_type": loss_type,
               "backbone": cfg["image_baseline"]["backbone"] if args.model == "image_only" else tc["backbone"],
               "best_epoch": stopper.best_epoch, "best_stage": best_stage, "best_val_macro_f1": stopper.best,
               "test": {}}
    rates = tc["eval_missing_rates"] if args.model == "fusion" else [0.0]
    frames = []
    for split, split_rates in (("val", [0.0]), ("test", rates)):
        for rate in split_rates:
            ev_adapt = make_fusion_adapt(fields, 0.0, 0.0, rate, args.seed) if args.model == "fusion" else adapt
            res = evaluate(model, loaders[split], loss_fn, device, ev_adapt, tc["amp"], args.max_batches)
            frames.append(predictions_frame(res, train_ds.classes, split, args.seed, rate))
            if split == "test":
                results["test"][f"missing_{rate}"] = {"loss": res["loss"], "macro_f1": res["macro_f1"],
                                                      "balanced_acc": res["balanced_acc"], "n": res["n"],
                                                      "n_image_failed": res["n_image_failed"]}
                log.info("test, %.0f%% of fields hidden: macro-F1 %.3f", 100 * rate, res["macro_f1"])
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    harness.main([str(out_dir / "predictions.csv"), "--n-boot", str(tc.get("n_boot", 1000))])
    return 0


def predictions_frame(res: dict, classes: list[str], split: str, seed: int, rate: float) -> pd.DataFrame:
    """Per-case predictions in the standard format read by evaluate.py (class names, not indices)."""
    return pd.DataFrame({
        "case_id": res["case_id"].astype(str), "split": split,
        "true_label": [classes[i] for i in res["y_true"]], "pred_label": [classes[i] for i in res["y_pred"]],
        "confidence": res["confidence"].round(6),
        "eFST": pd.Series(res["eFST"]).where(lambda s: s > 0).astype("Int64"),
        "eMST": pd.Series(res["eMST"]).where(lambda s: s > 0).astype("Int64"),
        "seed": seed, "missing_pct": rate})


if __name__ == "__main__":
    sys.exit(main())
