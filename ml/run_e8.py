"""Task 4.7 summary: fine-tuned DINOv2 and the two fixes of the Grad-CAM border artefact, against the app model.

Arms (all trained before, see run_e1.py ``arm_spec``):
  image_only             fine-tuned EfficientNet-B0 (E1 reference)
  probe_dinov2           frozen DINOv2 + linear probe, black padding (the app model, Task 4.5)
  probe_dinov2_reflect   the same probe on mirrored padding (``foundation_probe.py --pad-mode reflect``)
  probe_dinov2_reg       frozen DINOv2 with 4 register tokens + linear probe (Darcet et al., ICLR 2024)
  finetune_dinov2        DINOv2 with the top blocks fine-tuned (``run_finetune_dinov2.py``)

1. ``run_e1.py --no-train --name e8``: macro-F1 / balanced accuracy / ECE per arm and the paired
   differences against image_only and against probe_dinov2 (``results/e8/e8_summary.csv``,
   ``e8_table.md``), with the tone and category breakdown.
2. Calibration and abstention with the E4 rule (``run_e4.calibrate_seed``: temperature on the
   validation NLL, tau for 80% validation coverage): ECE after scaling, AURC, coverage, selective
   accuracy, and selective accuracy on eMST 4-6 minus 1-3 (the RQ4 gap), per arm and seed;
   paired AURC and selective-accuracy differences against probe_dinov2 (t interval over seeds).
   Written to ``results/e8/e8_calibration.csv`` and appended to ``e8_table.md``.

Grad-CAM of the new arms: ``run_gradcam.py --models probe_dinov2_reflect probe_dinov2_reg
finetune_dinov2 --out-dir results/e8/gradcam``.

Usage::

    python run_e8.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import run_e1  # noqa: E402
from data_loading import ROOT  # noqa: E402
from run_e4 import calibrate_seed, classes_of, load_arm  # noqa: E402
from skinconcern.metrics import emst_group  # noqa: E402

log = logging.getLogger("run_e8")
ARMS = ["image_only", "probe_dinov2", "probe_dinov2_reflect", "probe_dinov2_reg", "finetune_dinov2"]
REF = "probe_dinov2"


def calibration(arms: list[str], seeds: list[int], coverage: float) -> pd.DataFrame:
    rows = []
    for arm in arms:
        df = load_arm(arm, seeds)
        classes = classes_of(df)
        for s in seeds:
            test, info = calibrate_seed(df[df.seed == s], classes, coverage)
            g = test["eMST"].map(emst_group)
            sel = {k: test[(g == k) & test["answered"]]["correct"].mean() for k in ("1-3", "4-6")}
            rows.append({"arm": arm, "seed": s, **{k: info[k] for k in ("T", "tau", "ece_after", "aurc", "accuracy",
                                                                          "macro_f1", "coverage", "selective_accuracy")},
                         "sel_acc_gap_emst_4_6_vs_1_3": sel["4-6"] - sel["1-3"]})
    return pd.DataFrame(rows)


def markdown(cal: pd.DataFrame, arms: list[str]) -> str:
    cols = [("T", "T", 2), ("ece_after", "ECE after scaling", 3), ("aurc", "AURC", 3), ("coverage", "coverage", 3),
            ("selective_accuracy", "selective accuracy", 3), ("sel_acc_gap_emst_4_6_vs_1_3", "sel. acc. eMST 4-6 minus 1-3", 3)]
    out = ["", "## Calibration and abstention (E4 rule: temperature on validation NLL, tau for 80% validation coverage)",
           "", "Mean ± sd over seeds.", "", "| Arm | " + " | ".join(c[1] for c in cols) + " |",
           "|---|" + "---|" * len(cols)]
    for arm in arms:
        d = cal[cal.arm == arm]
        out.append(f"| {arm} | " + " | ".join(f"{d[c].mean():.{nd}f} ± {d[c].std(ddof=1):.{nd}f}" for c, _, nd in cols) + " |")
    out += ["", f"Paired difference against {REF} (mean [95% t interval over seeds], seeds where the arm is better, t p).",
            "", "| Arm | AURC | selective accuracy |", "|---|---|---|"]
    base = cal[cal.arm == REF].set_index("seed")
    for arm in arms:
        if arm == REF:
            continue
        d = cal[cal.arm == arm].set_index("seed")
        cells = []
        for c, better in (("aurc", -1), ("selective_accuracy", 1)):
            x = (d[c] - base[c]).dropna()
            lo, hi = stats.t.interval(0.95, len(x) - 1, loc=x.mean(), scale=stats.sem(x))
            cells.append(f"{x.mean():+.3f} [{lo:+.3f}, {hi:+.3f}], {(np.sign(x) == better).sum()}/{len(x)}, "
                         f"p = {stats.ttest_1samp(x, 0).pvalue:.3f}")
        out.append(f"| {arm} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", nargs="+", default=ARMS)
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--coverage", type=float, default=0.8)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e8")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_e1.main(["--no-train", "--arms", *args.arms, "--seeds", *map(str, args.seeds), "--out-dir", str(args.out_dir),
                 "--name", "e8"])
    cal = calibration(args.arms, args.seeds, args.coverage)
    cal.to_csv(args.out_dir / "e8_calibration.csv", index=False, float_format="%.5f")
    with open(args.out_dir / "e8_table.md", "a", encoding="utf-8") as f:
        f.write(markdown(cal, args.arms))
    log.info("wrote %s", args.out_dir / "e8_table.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
