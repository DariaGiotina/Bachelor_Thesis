"""Positive control: can the fusion model use the questionnaire at all when it is informative?

The real questionnaire gives no measurable gain (E1) and hiding all answers costs the fusion model
nothing (E2). Before blaming the data, this checks the method: one synthetic question is appended
to the real questionnaire, whose answer is the true category for a share ``agreement`` of the
cases and a random category otherwise (fixed per case, the same in every epoch, like a real answer).
The synthetic answer is a one-hot block of four columns plus one mask column, and it is hidden like
any other field (modality dropout in training, rate r at test time).

If the fusion model trained with this field clearly beats the photo-only model, the training
pipeline can exploit questionnaire information, and the null result of E1 is a property of the
real answers (weak or overlapping with the photo), not a bug. If it does not, the pipeline is at fault.

The synthetic field is never used outside this check. Outputs in
``runs/positive_control/agree<a>/seed<k>/`` (git-ignored) and
``results/e1/diagnostics/positive_control.csv`` / ``.md``.

Usage::

    python analysis/fusion_positive_control.py --seeds 0 1 2 --agreement 0.3 0.5
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from dropout_utils import make_dropout_adapt, training_rates  # noqa: E402
from engine import evaluate  # noqa: E402
from run_image_only import build_balanced_training, fit_staged  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from train import build_fusion, field_index  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("positive_control")


def synthetic_answer(case_id: torch.Tensor, label: torch.Tensor, agreement: float, n_classes: int,
                     seed: int) -> torch.Tensor:
    """Per case: the true class with probability ``agreement``, else a uniformly random class.

    Drawn from a generator keyed on (seed, case_id), so a case always gets the same answer.
    """
    out = torch.empty_like(label)
    for i, (cid, y) in enumerate(zip(case_id.tolist(), label.tolist())):
        rng = np.random.default_rng([seed, int(cid) % (2**63)])
        out[i] = y if rng.random() < agreement else int(rng.integers(n_classes))
    return out


def make_adapt(fields, rates, agreement, n_classes, seed, p_eval=0.0):
    """Appends the synthetic field to q_vec / q_mask, then applies the usual answer dropout."""
    inner = make_dropout_adapt(fields, rates, p_eval, seed)

    def adapt(batch: dict, training: bool) -> dict:
        ans = synthetic_answer(batch["case_id"], batch["label"], agreement, n_classes, seed)
        onehot = torch.nn.functional.one_hot(ans, n_classes).float()
        extra = {"q_vec": torch.cat([batch["q_vec"], onehot], 1),
                 "q_mask": torch.cat([batch["q_mask"], torch.zeros(len(ans), 1)], 1)}
        return inner({**batch, **extra}, training)

    return adapt


def run_seed(seed: int, agreement: float, cfg: dict, out_root: Path, device, epochs=None, max_batches=None) -> list[dict]:
    seed_everything(seed)
    loaders = get_dataloaders(cfg, seed)
    loss_fn, loaders = build_balanced_training("weighted_loss", cfg, seed, loaders, device, False)
    ds = loaders["train"].dataset
    k, n_q, n_f = len(ds.classes), len(ds.q_cols), len(ds.m_cols)
    fields = field_index(ds.q_cols, ds.m_cols) + [torch.arange(n_q, n_q + k)]  # synthetic field last
    rates = training_rates("fixed", cfg)
    model = build_fusion(cfg, k, n_q + k, n_f + 1).to(device)
    out_dir = out_root / f"agree{agreement:g}" / f"seed{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / "fusion_positive_control.pt"
    ckpt.unlink(missing_ok=True)
    fit = fit_staged(model, loaders, loss_fn, make_adapt(fields, rates, agreement, k, seed), cfg, ckpt, out_dir,
                     device, seed, epochs, max_batches)
    model.load_state_dict(torch.load(ckpt, map_location=device))
    rows = []
    for r in (0.0, 1.0):
        res = evaluate(model, loaders["test"], loss_fn, device, make_adapt(fields, rates, agreement, k, seed, r),
                       cfg["train"]["amp"], max_batches)
        rows.append({"seed": seed, "agreement": agreement, "missing_pct": r, "fusion_macro_f1": res["macro_f1"],
                     "best_epoch": fit["best_epoch"]})
    # macro-F1 of the synthetic answer on its own (how informative it is by itself)
    ys, ans = [], []
    for batch in loaders["test"]:
        ys.append(batch["label"])
        ans.append(synthetic_answer(batch["case_id"], batch["label"], agreement, k, seed))
    y, a = torch.cat(ys).numpy(), torch.cat(ans).numpy()
    for row in rows:
        row["synthetic_alone_macro_f1"] = float(f1_score(y, a, labels=np.unique(y), average="macro"))
    del model, loaders
    torch.cuda.empty_cache() if device.type == "cuda" else None
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--agreement", type=float, nargs="+", default=[0.3, 0.5])
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--max-batches", type=int, default=None)
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "positive_control")
    ap.add_argument("--results", type=Path, default=ROOT / "results" / "e1" / "diagnostics")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config(ROOT / "configs" / "base.yaml")
    if args.num_workers is not None:
        cfg["loader"]["num_workers"] = args.num_workers
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rows = [r for a in args.agreement for s in args.seeds
            for r in run_seed(s, a, cfg, args.out_root, device, args.epochs, args.max_batches)]
    df = pd.DataFrame(rows)
    photo = {}
    for s in args.seeds:  # photo-only test macro-F1 of the same seed (E1 runs)
        p = ROOT / "runs" / "e1_image_only" / "efficientnet_b0_weighted_loss" / "seed_runs.csv"
        if p.exists():
            sr = pd.read_csv(p)
            photo.update(dict(zip(sr["seed"], sr["test_macro_f1"])))
    df["photo_only_macro_f1"] = df["seed"].map(photo)
    df["gain_vs_photo"] = df["fusion_macro_f1"] - df["photo_only_macro_f1"]
    args.results.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.results / "positive_control.csv", index=False, float_format="%.4f")
    summ = df.groupby(["agreement", "missing_pct"])[["synthetic_alone_macro_f1", "photo_only_macro_f1",
                                                     "fusion_macro_f1", "gain_vs_photo"]].agg(["mean", "std"])
    lines = ["# Positive control: fusion with one synthetic informative question", "",
             f"Seeds {args.seeds}. agreement = share of cases whose synthetic answer is the true category "
             "(otherwise a random category). r = share of questions hidden at test time.", "",
             "| agreement | r | synthetic answer alone | photo only | fusion | fusion - photo |", "|---|---|---|---|---|---|"]
    for (a, r), row in summ.iterrows():
        lines.append(f"| {a:g} | {r:g} | {row[('synthetic_alone_macro_f1', 'mean')]:.3f} | "
                     f"{row[('photo_only_macro_f1', 'mean')]:.3f} | {row[('fusion_macro_f1', 'mean')]:.3f} ± "
                     f"{row[('fusion_macro_f1', 'std')]:.3f} | {row[('gain_vs_photo', 'mean')]:+.3f} |")
    text = "\n".join(lines) + "\n"
    (args.results / "positive_control.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
