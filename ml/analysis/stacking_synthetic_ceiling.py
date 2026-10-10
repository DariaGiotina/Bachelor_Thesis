"""How much can a questionnaire-strength signal add at best? Synthetic answers in the stacking combiner.

Uses the out-of-fold photo predictions of ``run_stacking.py`` (no retraining). The combiner of
``run_stacking.py`` (balanced logistic regression, C chosen on validation) is trained on the photo
log-probabilities plus one synthetic question whose answer is the true category for a share
``agreement`` of the cases and random otherwise (the same answers as in
``fusion_positive_control.py``). Its errors are independent of the photo by construction, so this
is the most favourable case for a question of that strength. Comparing with the photo-only combiner
(``stack_photo``) gives the ceiling of the gain such a question can bring on SCIN-sized data.

Agreement 0.3 gives a question with about the macro-F1 of the real questionnaire (0.38).

Outputs: ``results/e1/diagnostics/stacking_ceiling.csv`` and ``.md``.

Usage::

    python analysis/stacking_synthetic_ceiling.py --seeds 0 1 2 3 4 5 6 7 8 9
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import f1_score

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "analysis"))
from data_loading import ROOT, get_dataloaders, load_config  # noqa: E402
from fusion_positive_control import synthetic_answer  # noqa: E402
from run_stacking import fit_combiner  # noqa: E402


def macro_f1(y, p) -> float:
    return float(f1_score(y, p, labels=np.unique(y), average="macro"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--agreement", type=float, nargs="+", default=[0.2, 0.3, 0.4, 0.5])
    ap.add_argument("--stack-root", type=Path, default=ROOT / "runs" / "e1_stacking" / "efficientnet_b0_weighted_loss")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "e1" / "diagnostics")
    args = ap.parse_args(argv)
    cfg = load_config(ROOT / "configs" / "base.yaml")
    rows = []
    for seed in args.seeds:
        lp = dict(np.load(args.stack_root / f"seed{seed}" / "photo_logprobs.npz"))
        dss = {s: get_dataloaders(cfg, seed, s).dataset for s in ("train", "val", "test")}
        k = len(dss["train"].classes)
        y = {s: d.labels for s, d in dss.items()}
        photo_scaler, (_, _, photo_clf) = fit_combiner(lp["train"], y["train"], lp["val"], y["val"], seed)
        photo_f1 = macro_f1(y["test"], photo_clf.predict(photo_scaler.transform(lp["test"])))
        for a in args.agreement:
            syn = {s: np.eye(k)[synthetic_answer(torch.tensor([int(c) for c in d.case_ids]),
                                                 torch.from_numpy(d.labels.copy()), a, k, seed).numpy()]
                   for s, d in dss.items()}
            x = {s: np.c_[lp[s], syn[s]] for s in dss}
            sc, (_, c, clf) = fit_combiner(x["train"], y["train"], x["val"], y["val"], seed)
            rows.append({"seed": seed, "agreement": a,
                         "synthetic_alone_macro_f1": macro_f1(y["test"], syn["test"].argmax(1)),
                         "stack_photo_macro_f1": photo_f1,
                         "stack_photo_synthetic_macro_f1": macro_f1(y["test"], clf.predict(sc.transform(x["test"]))),
                         "C": c})
    df = pd.DataFrame(rows)
    df["gain"] = df["stack_photo_synthetic_macro_f1"] - df["stack_photo_macro_f1"]
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "stacking_ceiling.csv", index=False, float_format="%.4f")
    g = df.groupby("agreement")
    lines = ["# Ceiling: a synthetic question independent of the photo, in the stacking combiner", "",
             f"Seeds {args.seeds}. Test macro-F1, mean ± sd over seeds; gain = with the question minus photo only "
             "(same out-of-fold photo predictions); seeds better = seeds with a positive gain.", "",
             "| agreement | question alone | photo only (stack_photo) | photo + question | gain | seeds better |",
             "|---|---|---|---|---|---|"]
    for a, d in g:
        lines.append(f"| {a:g} | {d['synthetic_alone_macro_f1'].mean():.3f} | {d['stack_photo_macro_f1'].mean():.3f} | "
                     f"{d['stack_photo_synthetic_macro_f1'].mean():.3f} ± {d['stack_photo_synthetic_macro_f1'].std():.3f}"
                     f" | {d['gain'].mean():+.3f} ± {d['gain'].std():.3f} | {int((d['gain'] > 0).sum())}/{len(d)} |")
    text = "\n".join(lines) + "\n"
    (args.out / "stacking_ceiling.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
