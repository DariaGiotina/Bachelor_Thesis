"""E1 arm 2: questionnaire-only baseline over split seeds 0-4 (no image).

For every seed the script takes the same cases as the image models (``SCINDataset``, same split
variant, same dropped labels), trains ``QuestionnaireMLP`` on ``[q_vec, q_mask]`` with the epoch
functions of ``engine.py`` and early stopping on validation macro-F1, tests the best checkpoint once
and scores the predictions with ``evaluate.py``; the seeds are summarised as mean +- sd.

Imbalance correction (``--balance``) as in ``run_image_only.py``: class-weighted cross-entropy, or
plain cross-entropy with a ``WeightedRandomSampler``.

Missing answers: the test split is scored with a share r of the answered fields hidden, for every r
in ``train.eval_missing_rates`` (r = 0 is the natural missingness only; r = 1 hides everything, so
the prediction rests on the class balance alone). Fields are hidden with ``train.hide_answers`` and a
generator seeded per (seed, r) over batches of the same size and order as the fusion evaluation in
``train.py``, so both models see exactly the same hidden answers.

Outputs in ``runs/e1_questionnaire_only/<balance>/`` (git-ignored):
  seed_checkpoints/q_only_seed{seed}.pt   best-validation weights (state_dict)
  seed{seed}/log.csv, predictions.csv     training log; val + test predictions (evaluate.py format)
  seed{seed}/metrics_summary.*            evaluate.py on the test split
  seed_runs.csv                           best epoch / val macro-F1 / test macro-F1 per seed
  e1_questionnaire_only_test.csv          test metrics across seeds, per missing rate

Usage::

    python run_q_only.py
    python run_q_only.py --balance sampler --seeds 0 1 2 3 4
    python run_q_only.py --p-field-drop 0.15        # train with single answers hidden (robustness)
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import yaml
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, SCINDataset, load_config  # noqa: E402
from engine import EarlyStopping, evaluate, timed, train_one_epoch  # noqa: E402
from losses import class_weights  # noqa: E402
from models.q_model import QuestionnaireMLP  # noqa: E402
from run_image_only import BALANCES, aggregate_seeds, sample_weights, write_seed_runs  # noqa: E402
from train import field_index, hide_answers, predictions_frame  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_q_only")


class QuestionnaireDataset(Dataset):
    """The questionnaire part of a ``SCINDataset`` split (no image is read)."""

    def __init__(self, scin: SCINDataset):
        self.classes, self.q_cols, self.m_cols = scin.classes, scin.q_cols, scin.m_cols
        self.q_vec, self.q_mask = torch.from_numpy(scin.q_vec), torch.from_numpy(scin.q_mask)
        self.labels = scin.labels
        self.y, self.efst, self.emst = (torch.from_numpy(a) for a in (scin.labels, scin.efst, scin.emst))
        self.case_ids = torch.tensor([int(c) for c in scin.case_ids], dtype=torch.int64)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, i: int) -> dict:
        return {"q_vec": self.q_vec[i], "q_mask": self.q_mask[i], "label": self.y[i], "eFST": self.efst[i],
                "eMST": self.emst[i], "case_id": self.case_ids[i]}


def make_q_adapt(fields: list[torch.Tensor], p_field_train: float, p_field_eval: float, seed: int):
    """Batch -> model kwargs; hides single answers like ``train.make_fusion_adapt`` (same generator use)."""
    gen = torch.Generator().manual_seed(seed)

    def adapt(batch: dict, training: bool) -> dict:
        pf = p_field_train if training else p_field_eval
        q_vec, q_mask = batch["q_vec"], batch["q_mask"]
        if pf > 0:
            q_vec, q_mask = hide_answers(q_vec, q_mask, fields, 0.0, pf, gen)
        return {"q_vec": q_vec, "q_mask": q_mask}

    return adapt


def build_loaders(cfg: dict, seed: int, balance: str, only_available: bool) -> dict:
    lc = cfg["loader"]
    out = {}
    for split in ("train", "val", "test"):
        ds = QuestionnaireDataset(SCINDataset(cfg, split, seed, only_available))
        gen = torch.Generator().manual_seed(seed)
        if split == "train" and balance == "sampler":
            sampler = WeightedRandomSampler(sample_weights(ds.labels, len(ds.classes)), num_samples=len(ds),
                                            replacement=True, generator=gen)
            out[split] = DataLoader(ds, batch_size=lc["batch_size"], sampler=sampler)
        else:  # same batch size and (for val/test) order as the image loaders
            out[split] = DataLoader(ds, batch_size=lc["batch_size"], shuffle=(split == "train"), generator=gen)
    return out


def train_seed(seed: int, cfg: dict, opts: dict, out_dir: Path, ckpt: Path, device: torch.device) -> tuple[dict, list]:
    seed_everything(seed)
    qc, tc = cfg["q_baseline"], cfg["train"]
    loaders = build_loaders(cfg, seed, opts["balance"], opts["only_available"])
    train_ds = loaders["train"].dataset
    classes, n_classes = train_ds.classes, len(train_ds.classes)
    fields = field_index(train_ds.q_cols, train_ds.m_cols)
    loss_fn = (nn.CrossEntropyLoss(weight=class_weights(train_ds.labels, n_classes).to(device))
               if opts["balance"] == "weighted_loss" else nn.CrossEntropyLoss())
    model = QuestionnaireMLP(len(train_ds.q_cols), len(train_ds.m_cols), n_classes, qc["hidden"], qc["depth"],
                             qc["dropout"]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=qc["lr"], weight_decay=qc["weight_decay"])
    scaler = torch.amp.GradScaler(enabled=False)  # tiny model: full precision
    adapt = make_q_adapt(fields, opts["p_field_drop"], 0.0, seed)
    log.info("seed %d | %s | train=%d val=%d test=%d | %d features + %d mask columns", seed, opts["balance"],
             len(train_ds), len(loaders["val"].dataset), len(loaders["test"].dataset), len(train_ds.q_cols),
             len(train_ds.m_cols))

    stopper, history, t0 = EarlyStopping(qc["early_stopping_patience"]), [], time.time()
    epochs = opts["epochs"] or qc["epochs"]
    for epoch in range(epochs):
        train_loss, secs = timed(train_one_epoch, model, loaders["train"], loss_fn, opt, scaler, device, adapt,
                                 False, tc["grad_clip"], opts["max_batches"])
        val = evaluate(model, loaders["val"], loss_fn, device, adapt, False, opts["max_batches"])
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val["loss"],
                        "val_macro_f1": val["macro_f1"], "val_balanced_acc": val["balanced_acc"],
                        "epoch_time": round(secs, 2)})
        if stopper.step(val["macro_f1"], epoch):
            torch.save(model.state_dict(), ckpt)
        if stopper.should_stop:
            break
    pd.DataFrame(history).to_csv(out_dir / "log.csv", index=False)
    log.info("seed %d: best epoch %d of %d, val macro-F1 %.3f", seed, stopper.best_epoch, len(history), stopper.best)

    model.load_state_dict(torch.load(ckpt, map_location=device))
    frames, test = [], {}
    for split, rates in (("val", [0.0]), ("test", tc["eval_missing_rates"])):
        for rate in rates:
            ev = make_q_adapt(fields, 0.0, rate, seed)  # fresh generator per rate, as in train.py
            res = evaluate(model, loaders[split], loss_fn, device, ev, False, opts["max_batches"])
            frames.append(predictions_frame(res, classes, split, seed, rate))
            if split == "test":
                test[f"test_macro_f1_missing_{rate}"] = res["macro_f1"]
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    summary = {"seed": seed, "best_epoch": stopper.best_epoch, "epochs_run": len(history),
               "best_val_macro_f1": stopper.best, "train_seconds": round(time.time() - t0, 1), **test}
    return summary, history


def run(options: dict | None = None) -> pd.DataFrame:
    defaults = {"config": ROOT / "configs" / "base.yaml", "balance": "weighted_loss", "seeds": [0, 1, 2, 3, 4],
                "out_root": ROOT / "runs" / "e1_questionnaire_only", "epochs": None, "max_batches": None,
                "n_boot": None, "only_available": False, "p_field_drop": None,
                "skip_existing": False}
    opts = {**defaults, **(options or {})}
    if opts["balance"] not in BALANCES:
        raise ValueError(f"balance must be one of {BALANCES}, got {opts['balance']!r}")
    cfg = copy.deepcopy(load_config(opts["config"]))
    if opts["p_field_drop"] is None:
        opts["p_field_drop"] = cfg["q_baseline"]["p_field_drop"]
    n_boot = opts["n_boot"] or cfg["train"].get("n_boot", 1000)
    exp = opts["balance"] + (f"_fielddrop{opts['p_field_drop']:g}" if opts["p_field_drop"] > 0 else "")
    root = Path(opts["out_root"]) / exp
    (root / "seed_checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info("E1 questionnaire-only | %s | seeds %s | device %s | out %s", exp, opts["seeds"], device, root)

    runs, flats = [], []
    for seed in opts["seeds"]:
        out_dir, ckpt = root / f"seed{seed}", root / "seed_checkpoints" / f"q_only_seed{seed}.pt"
        out_dir.mkdir(exist_ok=True)
        if opts["skip_existing"] and ckpt.exists() and (out_dir / "metrics_summary.csv").exists():
            log.info("seed %d already done, skipped (--skip-existing)", seed)
        else:
            ckpt.unlink(missing_ok=True)  # never start from another run's weights
            summary, _ = train_seed(seed, cfg, opts, out_dir, ckpt, device)
            runs.append({"balance": opts["balance"], "p_field_drop": opts["p_field_drop"], **summary})
            write_seed_runs(root / "seed_runs.csv", runs[-1:])
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", str(n_boot)])
        flats.append(pd.read_csv(out_dir / "metrics_summary.csv", dtype={"seed": str}))

    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    summary.insert(0, "experiment", "E1_questionnaire_only")
    summary.insert(1, "balance", opts["balance"])
    summary.insert(2, "p_field_drop", opts["p_field_drop"])
    summary.to_csv(root / "e1_questionnaire_only_test.csv", index=False)
    (root / "run_options.json").write_text(json.dumps({k: str(v) for k, v in opts.items()}, indent=2),
                                           encoding="utf-8")
    head = summary[(summary["scope"] == "overall") & (summary["metric"] == "macro_f1")]
    for _, r in head.iterrows():
        log.info("test macro-F1, %3.0f%% of answers hidden: %s (n_seeds=%d)", 100 * r["missing_pct"],
                 r["mean_pm_sd"], r["n_seeds"])
    log.info("wrote %s", root / "e1_questionnaire_only_test.csv")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "e1_questionnaire_only")
    ap.add_argument("--epochs", type=int, default=None, help="maximum epochs (default: config)")
    ap.add_argument("--p-field-drop", type=float, default=None, help="hide single answers in training")
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--n-boot", type=int, default=None, help="bootstrap resamples for evaluate.py")
    ap.add_argument("--only-available", action="store_true", help="only cases whose images exist (as the image runs)")
    ap.add_argument("--skip-existing", action="store_true", help="reuse seeds that already have results")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(vars(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
