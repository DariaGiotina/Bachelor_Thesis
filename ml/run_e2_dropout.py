"""E2 / Task 3.4: does training with hidden answers keep the fusion model reliable when answers are missing?

Compares, on the same test cases per split seed, three trainings of one fusion variant
(``run_fusion.py --q_dropout``) and the photo-only model:

  nodrop    no answers hidden in training                    fusion_<variant>_nodrop
  fixed     fixed rates (questionnaire 30%, field 15%; E1)   fusion_<variant>
  randdrop  field-drop rate sampled 0-100% per batch, plus
            whole questionnaire hidden for 10% of cases      fusion_<variant>_randdrop
  image_only (reference line: it never reads the questionnaire, so it is the same at every rate)

For every test missing rate r (share of fields hidden at test time, on top of the naturally missing
answers; same hidden answers for every model) it reports macro-F1 per arm (mean +- sd over seeds,
seed-stratified case-bootstrap 95% CI) and paired differences (randdrop - nodrop, randdrop - fixed,
fixed - nodrop, every fusion arm - image_only) with paired bootstrap CIs and t-tests over seeds. It
also reports the loss from r = 0 to r = 1 per arm, and, per skin-tone group (eFST, eMST), the
macro-F1 at r = 0 and r = 1 with the paired difference of randdrop and fixed against nodrop
(t-test over seeds, Holm-adjusted within each comparison).

Outputs: ``results/e2/e2_<variant>_summary.csv`` and ``results/e2/e2_<variant>_table.md``.

Usage::

    python run_e2_dropout.py                           # concat, seeds 0-9 (trains missing arms)
    python run_e2_dropout.py --variant film --no-train
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
from data_loading import ROOT  # noqa: E402
from models.fusion_model import FUSIONS  # noqa: E402
from run_e1 import SCALES, arm_spec, encode, holm, load_predictions, metrics_matrix, seed_draws  # noqa: E402
from run_image_only import BACKBONES, BALANCES  # noqa: E402
from skinconcern.metrics import _fast_metrics  # noqa: E402

log = logging.getLogger("run_e2_dropout")
LABELS = {"nodrop": "_nodrop", "fixed": "", "randdrop": "_randdrop"}
PAIRS = [("randdrop", "nodrop"), ("randdrop", "fixed"), ("fixed", "nodrop"),
         ("nodrop", "image_only"), ("fixed", "image_only"), ("randdrop", "image_only")]


def arm_frames(variant: str, backbone: str, balance: str, seeds: list[int], train: bool) -> pd.DataFrame:
    frames = []
    for label, suffix in {"image_only": None, **LABELS}.items():
        arm = "image_only" if suffix is None else f"fusion_{variant}{suffix}"
        spec = arm_spec(arm, backbone, balance)
        if train:
            spec["train"]({"balance": balance, "seeds": seeds, "skip_existing": True})
        frames.append(load_predictions(arm, spec, seeds).assign(arm=label))
    return pd.concat(frames, ignore_index=True)


def by_rate(preds: pd.DataFrame, arm: str, rate: float, seeds: list[int], classes: list[str]) -> dict:
    """Integer-coded (true, pred, confidence) per seed; image_only is read at r = 0 for every rate."""
    d = preds[(preds["arm"] == arm) & (preds["missing_pct"] == (0.0 if arm == "image_only" else rate))]
    return {s: encode(d[d["seed"] == s].sort_values("case_id"), classes) for s in seeds}


def overall(preds, arms, rates, seeds, classes, n_boot, boot_seed) -> pd.DataFrame:
    k = len(classes)
    ref = {s: preds[(preds["arm"] == "image_only") & (preds["seed"] == s)]["case_id"].sort_values().to_numpy()
           for s in seeds}
    for arm in arms:  # every arm must be scored on the same cases
        for s in seeds:
            ids = preds[(preds["arm"] == arm) & (preds["seed"] == s) & (preds["missing_pct"] == 0.0)]["case_id"]
            if not np.array_equal(ids.sort_values().to_numpy(), ref[s]):
                raise ValueError(f"{arm} seed {s} was tested on different cases than image_only")
    draws = seed_draws({s: len(ref[s]) for s in seeds}, n_boot, boot_seed)
    point, boot, rows = {}, {}, []
    for arm in arms:
        for r in rates:
            arr = by_rate(preds, arm, r, seeds, classes)
            point[(arm, r)] = np.array([_fast_metrics(*arr[s], k, 15)[0] for s in seeds])
            boot[(arm, r)] = np.stack([metrics_matrix(*arr[s], k, draws[s], 15)[:, 0] for s in seeds])  # (S, B)
            pt, bt = point[(arm, r)], np.nanmean(boot[(arm, r)], axis=0)
            rows.append({"row_type": "arm", "arm": arm, "versus": "", "missing_pct": r, "mean": pt.mean(),
                         "sd": pt.std(ddof=1), "ci_low": np.quantile(bt, 0.025), "ci_high": np.quantile(bt, 0.975),
                         **{f"seed{s}": v for s, v in zip(seeds, pt)}})

    def paired(row_type, a_key, b_key, arm, versus, r):
        d_pt = point[a_key] - point[b_key]
        d_bt = np.nanmean(boot[a_key] - boot[b_key], axis=0)
        return {"row_type": row_type, "arm": arm, "versus": versus, "missing_pct": r, "mean": d_pt.mean(),
                "sd": d_pt.std(ddof=1), "ci_low": np.quantile(d_bt, 0.025), "ci_high": np.quantile(d_bt, 0.975),
                "a_better_seeds": int((d_pt > 0).sum()),
                "t_test_p": stats.ttest_rel(point[a_key], point[b_key]).pvalue if np.std(d_pt) > 0 else np.nan,
                **{f"seed{s}": v for s, v in zip(seeds, d_pt)}}

    for a, b in PAIRS:
        rows += [paired("paired", (a, r), (b, r), a, b, r) for r in rates]
    for arm in arms:  # robustness: macro-F1 lost when every answer is hidden
        if arm != "image_only":
            rows.append(paired("drop_r1_vs_r0", (arm, max(rates)), (arm, 0.0), arm, "same arm at r=0", max(rates)))
    return pd.DataFrame(rows)


def tone_groups(preds, seeds, classes, rates=(0.0, 1.0)) -> pd.DataFrame:
    """Macro-F1 per skin-tone group at r = 0 and r = 1, and paired differences against nodrop."""
    k = len(classes)
    code = {c: i for i, c in enumerate(classes)}
    point = {}
    for arm in ["image_only", *LABELS]:
        for r in rates:
            d = preds[(preds["arm"] == arm) & (preds["missing_pct"] == (0.0 if arm == "image_only" else r))]
            for s in seeds:
                ds = d[d["seed"] == s]
                for scale, (fn, groups) in SCALES.items():
                    g = ds[scale].map(fn).to_numpy()
                    for grp in groups:
                        m = g == grp
                        t, p = ds["true_label"].map(code).to_numpy()[m], ds["pred_label"].map(code).to_numpy()[m]
                        v = _fast_metrics(t, p, ds["confidence"].to_numpy(float)[m], k, 15)[0] if m.sum() > 1 else np.nan
                        point.setdefault((arm, r, scale, grp), []).append(v)
                        point.setdefault(("n", r, scale, grp), []).append(int(m.sum()))
    rows = []
    units = [(scale, g) for scale, (_, gs) in SCALES.items() for g in gs]
    for arm in ["image_only", *LABELS]:
        for r in rates:
            for scale, g in units:
                pt = np.array(point[(arm, r, scale, g)])
                rows.append({"row_type": "arm_group", "arm": arm, "versus": "", "missing_pct": r, "scale": scale,
                             "group": g, "mean_n_cases": np.mean(point[("n", r, scale, g)]),
                             "mean": np.nanmean(pt), "sd": np.nanstd(pt, ddof=1)})
    for arm in ("randdrop", "fixed"):
        fam = []
        for r in rates:
            for scale, g in units:
                d = np.array(point[(arm, r, scale, g)]) - np.array(point[("nodrop", r, scale, g)])
                ok = ~np.isnan(d)
                tp = stats.ttest_1samp(d[ok], 0).pvalue if ok.sum() > 1 and np.std(d[ok]) > 0 else np.nan
                fam.append({"row_type": "paired_group", "arm": arm, "versus": "nodrop", "missing_pct": r,
                            "scale": scale, "group": g, "mean": np.nanmean(d), "sd": np.nanstd(d, ddof=1),
                            "a_better_seeds": int((d[ok] > 0).sum()), "t_test_p": tp})
        for row, h in zip(fam, holm([x["t_test_p"] for x in fam])):
            row["holm_p"] = h
        rows += fam
    return pd.DataFrame(rows)


def markdown(tab: pd.DataFrame, groups: pd.DataFrame, meta: dict) -> str:
    def f(x, nd=3):
        return "" if pd.isna(x) else f"{x:.{nd}f}"

    rates = sorted(tab["missing_pct"].unique())
    out = [f"# E2: answer dropout in training ({meta['variant']} fusion, {meta['backbone']}, {meta['balance']})", "",
           f"Seeds: {meta['seeds']}. Test macro-F1, mean ± sd over seeds [seed-stratified bootstrap 95% CI]. "
           "r = share of questionnaire fields hidden at test time (on top of the naturally missing ones). "
           "image_only does not read the questionnaire, so its value is the same at every r.", "",
           "| arm | " + " | ".join(f"r = {r:g}" for r in rates) + " |", "|---" * (len(rates) + 1) + "|"]
    arms = tab[tab["row_type"] == "arm"]
    for arm in ["image_only", *LABELS]:
        cells = [arms[(arms["arm"] == arm) & (arms["missing_pct"] == r)].iloc[0] for r in rates]
        out.append(f"| {arm} | " + " | ".join(f"{f(c['mean'])} ± {f(c['sd'])} [{f(c['ci_low'])}, {f(c['ci_high'])}]"
                                              for c in cells) + " |")
    out += ["", "## Paired differences (A - B, macro-F1)", "",
            "| A vs B | r | mean diff | 95% CI | A better (seeds) | t-test p |", "|---|---|---|---|---|---|"]
    pr = tab[tab["row_type"] == "paired"]
    for _, r in pr.iterrows():
        out.append(f"| {r['arm']} vs {r['versus']} | {r['missing_pct']:g} | {r['mean']:+.3f} | "
                   f"[{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | {int(r['a_better_seeds'])}/{len(meta['seeds'])} | "
                   f"{f(r['t_test_p'])} |")
    out += ["", "## Robustness: macro-F1 change from r = 0 to r = 1 (all answers hidden)", "",
            "| arm | change | 95% CI |", "|---|---|---|"]
    for _, r in tab[tab["row_type"] == "drop_r1_vs_r0"].iterrows():
        out.append(f"| {r['arm']} | {r['mean']:+.3f} | [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] |")
    out += ["", "## Skin-tone groups (macro-F1 mean over seeds; paired diff vs nodrop, Holm-adjusted p)", "",
            "| scale | group | r | n cases | image_only | nodrop | fixed | randdrop | fixed - nodrop (p_Holm) | "
            "randdrop - nodrop (p_Holm) |", "|---|---|---|---|---|---|---|---|---|---|"]
    ag, pg = groups[groups["row_type"] == "arm_group"], groups[groups["row_type"] == "paired_group"]
    for (scale, g, r), blk in ag.groupby(["scale", "group", "missing_pct"], sort=False):
        val = {row["arm"]: row["mean"] for _, row in blk.iterrows()}
        diff = {row["arm"]: row for _, row in pg[(pg["scale"] == scale) & (pg["group"] == g)
                                                  & (pg["missing_pct"] == r)].iterrows()}
        out.append(f"| {scale} | {g} | {r:g} | {blk['mean_n_cases'].iloc[0]:.1f} | {f(val['image_only'])} | "
                   f"{f(val['nodrop'])} | {f(val['fixed'])} | {f(val['randdrop'])} | "
                   f"{diff['fixed']['mean']:+.3f} ({f(diff['fixed']['holm_p'])}) | "
                   f"{diff['randdrop']['mean']:+.3f} ({f(diff['randdrop']['holm_p'])}) |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variant", choices=FUSIONS, default="concat")
    ap.add_argument("--backbone", choices=BACKBONES, default="efficientnet_b0")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--no-train", action="store_true", help="only build the tables from existing runs")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--boot-seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e2")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    preds = arm_frames(args.variant, args.backbone, args.balance, args.seeds, not args.no_train)
    classes = sorted(set(preds["true_label"]) | set(preds["pred_label"]))
    rates = sorted(preds.loc[preds["arm"] == "nodrop", "missing_pct"].unique())
    arms = ["image_only", *LABELS]
    tab = overall(preds, arms, rates, args.seeds, classes, args.n_boot, args.boot_seed)
    groups = tone_groups(preds, args.seeds, classes)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"variant": args.variant, "backbone": args.backbone, "balance": args.balance, "seeds": args.seeds}
    pd.concat([tab, groups], ignore_index=True).to_csv(args.out_dir / f"e2_{args.variant}_summary.csv",
                                                       index=False, float_format="%.5f")
    text = markdown(tab, groups, meta)
    (args.out_dir / f"e2_{args.variant}_table.md").write_text(text, encoding="utf-8")
    log.info("wrote %s", args.out_dir / f"e2_{args.variant}_table.md")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
