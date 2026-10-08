"""Train and evaluate the photo (+ questionnaire) skin-concern classifier on one split seed.

The model is the late-fusion network of ``skinconcern.model``: an image backbone plus a
questionnaire branch. The questionnaire input is ``[q_vec, q_mask]`` (features + per-field
missing flags). During training, answers are hidden on purpose (modality dropout): a whole
questionnaire with probability ``p_modality_drop`` and single fields with ``p_field_drop``;
hidden fields get zero features and mask 1, exactly like a real missing answer.

After training, the best-validation checkpoint is evaluated once on the test split, overall and
per eFST group, at several simulated missing-answer rates.

Usage::

    python train.py --seed 0                       # questionnaire model, config defaults
    python train.py --seed 0 --image-only          # photo-only baseline
    python train.py --epochs 2 --max-batches 5 --only-available --num-workers 0   # smoke test
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import balanced_accuracy_score, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from skinconcern.metrics import max_gap, stratified_report  # noqa: E402
from skinconcern.model import FusionClassifier  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("train")
EFST_NAMES = {1: "I-II", 2: "I-II", 3: "III-IV", 4: "III-IV", 5: "V-VI", 6: "V-VI"}


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


def model_input(batch, fields, p_modality, p_field, device, gen=None):
    q_vec, q_mask = batch["q_vec"], batch["q_mask"]
    if p_modality > 0 or p_field > 0:
        q_vec, q_mask = hide_answers(q_vec, q_mask, fields, p_modality, p_field, gen)
    return torch.cat([q_vec, q_mask], dim=1).to(device)


@torch.no_grad()
def predict(model, loader, fields, device, p_missing: float, use_q: bool, seed: int, max_batches=None):
    model.eval()
    gen = torch.Generator().manual_seed(seed)
    ys, ps, ef = [], [], []
    for b, batch in enumerate(loader):
        if max_batches and b >= max_batches:
            break
        q = model_input(batch, fields, p_missing, 0.0, device, gen) if use_q else None
        logits = model(batch["image"].to(device), q)
        ys.append(batch["label"].numpy())
        ps.append(logits.argmax(1).cpu().numpy())
        ef.append(batch["eFST"].numpy())
    return np.concatenate(ys), np.concatenate(ps), np.concatenate(ef)


def scores(y, p) -> dict:
    return {"macro_f1": float(f1_score(y, p, average="macro")),
            "balanced_acc": float(balanced_accuracy_score(y, p)), "n": int(len(y))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--image-only", action="store_true", help="photo-only baseline (no questionnaire)")
    ap.add_argument("--p-modality-drop", type=float, default=None)
    ap.add_argument("--p-field-drop", type=float, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--only-available", action="store_true", help="skip cases whose images are missing")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config(args.config)
    tc = cfg["train"]
    epochs = args.epochs or tc["epochs"]
    p_mod = tc["p_modality_drop"] if args.p_modality_drop is None else args.p_modality_drop
    p_fld = tc["p_field_drop"] if args.p_field_drop is None else args.p_field_drop
    use_q = not args.image_only
    if args.num_workers is not None:
        tmp = args.config.with_name("_tmp_train.yaml")
        cfg["loader"]["num_workers"] = args.num_workers
        import yaml
        tmp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        args.config = tmp
    name = f"{'image_only' if args.image_only else 'fusion'}_seed{args.seed}"
    out_dir = args.out_dir or ROOT / "runs" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:
        loaders = get_dataloaders(args.config, args.seed, only_available=args.only_available)
    finally:
        if args.config.name == "_tmp_train.yaml":
            args.config.unlink(missing_ok=True)
    train_ds = loaders["train"].dataset
    fields = field_index(train_ds.q_cols, train_ds.m_cols)
    n_classes = len(train_ds.classes)
    n_q = len(train_ds.q_cols) + len(train_ds.m_cols)

    model = FusionClassifier(n_classes, n_q, tc["backbone"], tc["pretrained"], tc["q_hidden"],
                             p_dropout=0.0, use_questionnaire=use_q).to(device)
    counts = np.bincount(train_ds.labels, minlength=n_classes).astype(np.float32)
    weights = torch.tensor(counts.sum() / (n_classes * np.maximum(counts, 1)), device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)  # classes are imbalanced
    opt = torch.optim.AdamW(model.parameters(), lr=tc["lr"], weight_decay=tc["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    scaler = torch.amp.GradScaler(enabled=device.type == "cuda")
    log.info("%s | device=%s classes=%s train=%d val=%d test=%d", name, device, train_ds.classes,
             len(train_ds), len(loaders["val"].dataset), len(loaders["test"].dataset))

    best_f1, history = -1.0, []
    for epoch in range(epochs):
        model.train()
        train_ds.set_epoch(epoch)
        t0, running, nb = time.time(), 0.0, 0
        gen = torch.Generator().manual_seed(args.seed * 1000 + epoch)
        for b, batch in enumerate(loaders["train"]):
            if args.max_batches and b >= args.max_batches:
                break
            q = model_input(batch, fields, p_mod, p_fld, device, gen) if use_q else None
            with torch.autocast(device.type, enabled=device.type == "cuda"):
                loss = loss_fn(model(batch["image"].to(device), q), batch["label"].to(device))
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            running, nb = running + loss.item(), nb + 1
        sched.step()
        y, p, _ = predict(model, loaders["val"], fields, device, 0.0, use_q, args.seed, args.max_batches)
        val = scores(y, p)
        history.append({"epoch": epoch, "train_loss": running / max(nb, 1), **{f"val_{k}": v for k, v in val.items()},
                        "seconds": round(time.time() - t0, 1)})
        log.info("epoch %d loss %.4f val macro-F1 %.3f bal-acc %.3f (%.0fs)", epoch, history[-1]["train_loss"],
                 val["macro_f1"], val["balanced_acc"], history[-1]["seconds"])
        if val["macro_f1"] > best_f1:
            best_f1 = val["macro_f1"]
            torch.save(model.state_dict(), out_dir / "best.pt")
    pd.DataFrame(history).to_csv(out_dir / "history.csv", index=False)

    # One final test evaluation with the best-validation weights.
    model.load_state_dict(torch.load(out_dir / "best.pt", map_location=device))
    results = {"run": name, "seed": args.seed, "best_val_macro_f1": best_f1, "test": {}}
    rates = tc["eval_missing_rates"] if use_q else [0.0]
    for rate in rates:
        y, p, ef = predict(model, loaders["test"], fields, device, rate, use_q, args.seed, args.max_batches)
        groups = [EFST_NAMES.get(int(e), "missing") for e in ef]
        rep = stratified_report(y, p, groups)
        results["test"][f"missing_{rate}"] = {
            **scores(y, p), "max_gap_macro_f1": max_gap(rep),
            "by_efst_group": rep.set_index("group")[["n", "macro_f1", "balanced_acc"]].round(4).to_dict("index")}
        rep.to_csv(out_dir / f"test_by_efst_missing_{rate}.csv", index=False)
        log.info("test, answers hidden %.0f%%: macro-F1 %.3f", 100 * rate, results["test"][f"missing_{rate}"]["macro_f1"])
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
