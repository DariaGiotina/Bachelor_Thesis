"""E1 runner and comparison table: photo only vs questionnaire only vs fusion (RQ1).

1. Trains every requested arm over split seeds 0-4 with the existing runners (seeds that already
   have results are reused, so the script can be re-run after an interruption):
     image_only              run_image_only.py
     questionnaire_only      run_q_only.py
     fusion_<variant>        run_fusion.py --fusion <variant>          (concat, gated, film)
     fusion_<variant>_nodrop run_fusion.py --fusion <variant> --q_dropout none
     fusion_<variant>_randdrop run_fusion.py --fusion <variant> --q_dropout random (Task 3.4)
     stack_photo, stack_photo_q, stack_q, stack_photo_qmlp
                             run_stacking.py (cross-fitted stacking: out-of-fold photo predictions
                             + questionnaire in a logistic-regression combiner)
     ensemble_image_q        ensemble_image_q.py (diagnostic: the two single-input models combined,
                             weight chosen on validation; no retraining)
   All arms share the backbone and imbalance correction given here.
2. Merges the per-seed test predictions of all arms. Every arm is tested on exactly the same cases
   per seed (same split variant); the script checks this.
3. Writes ``results/e1/e1_summary.csv`` and ``results/e1/e1_table.md`` (aggregate numbers only):
   * one row per arm and metric (macro-F1, balanced accuracy, accuracy, ECE; with all answers, and
     macro-F1 with every answer hidden for arms that read the questionnaire): mean and standard
     deviation over seeds, and a 95% CI from a seed-stratified case bootstrap (cases are resampled
     within each seed's test set, the metric is averaged over seeds; the CI reflects test-set
     sampling, the standard deviation reflects training randomness);
   * one row per pair of arms: the per-seed macro-F1 difference (A - B) on the shared test cases,
     each with a paired case-bootstrap CI (both models scored on the same resampled cases), the mean
     difference with a seed-stratified paired bootstrap CI, the number of seeds where A wins, and a
     paired t-test and Wilcoxon signed-rank test over seeds;
   * per skin-tone group (eFST I-II / III-IV / V-VI, eMST 1-3 / 4-6 / 7-10) the macro-F1, and per
     category the F1, of every arm, and the paired difference of every arm against image_only,
     with Holm-adjusted p-values (family = all groups and categories of one comparison).

Usage::

    python run_e1.py                                    # image, questionnaire, fusion concat + gated
    python run_e1.py --arms image_only questionnaire_only fusion_concat fusion_gated fusion_film fusion_concat_nodrop
    python run_e1.py --no-train                         # only rebuild the tables from existing runs
"""
from __future__ import annotations

import argparse
import itertools
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT  # noqa: E402
from models.fusion_model import FUSIONS  # noqa: E402
from run_image_only import BACKBONES, BALANCES  # noqa: E402
from skinconcern.metrics import (FAST_NAMES, _fast_metrics, bias_corrected_ci, efst_group,  # noqa: E402
                                 emst_group)

log = logging.getLogger("run_e1")
DEFAULT_ARMS = ["image_only", "questionnaire_only", "fusion_concat", "fusion_gated"]
REFERENCE_PAIRS = [("fusion", "image_only"), ("fusion", "questionnaire_only"), ("image_only", "questionnaire_only")]


# ------------------------------------------------------------------------------------------- arms
def arm_spec(arm: str, backbone: str, balance: str) -> dict:
    """Run folder, training call and whether the arm reads the questionnaire."""
    if arm == "image_only":
        return {"dir": ROOT / "runs" / "e1_image_only" / f"{backbone}_{balance}", "questionnaire": False,
                "train": lambda o: __import__("run_image_only").run({**o, "backbone": backbone})}
    if arm == "questionnaire_only":
        return {"dir": ROOT / "runs" / "e1_questionnaire_only" / balance, "questionnaire": True,
                "train": lambda o: __import__("run_q_only").run(o)}
    if arm == "ensemble_image_q":  # diagnostic: photo-only x questionnaire-only probabilities (ensemble_image_q.py)
        return {"dir": ROOT / "runs" / "e1_ensemble" / f"{backbone}_{balance}", "questionnaire": True,
                "train": lambda o: __import__("ensemble_image_q").run({**o, "backbone": backbone})}
    if arm in ("stack_photo", "stack_photo_q", "stack_q", "stack_photo_qmlp"):  # cross-fitted stacking (run_stacking.py)
        return {"dir": ROOT / "runs" / "e1_stacking" / f"{backbone}_{balance}" / arm, "questionnaire": arm != "stack_photo",
                "train": lambda o: __import__("run_stacking").run({**o, "backbone": backbone})}
    if arm.startswith("fusion_"):
        variant, mode = arm.removeprefix("fusion_"), "fixed"
        for suffix, m in (("_nodrop", "none"), ("_randdrop", "random")):
            if variant.endswith(suffix):
                variant, mode = variant.removesuffix(suffix), m
        if variant not in FUSIONS:
            raise ValueError(f"unknown fusion variant in {arm!r} (choose from {FUSIONS})")
        name = f"{backbone}_{variant}_{balance}" + {"none": "_nodrop", "fixed": "", "random": "_randdrop"}[mode]
        return {"dir": ROOT / "runs" / "e1_fusion" / name, "questionnaire": True,
                "train": lambda o: __import__("run_fusion").run({**o, "backbone": backbone, "fusion": variant,
                                                                  "q_dropout": mode})}
    raise ValueError(f"unknown arm {arm!r}")


def load_predictions(arm: str, spec: dict, seeds: list[int]) -> pd.DataFrame:
    frames = []
    for seed in seeds:
        path = spec["dir"] / f"seed{seed}" / "predictions.csv"
        if not path.exists():
            raise FileNotFoundError(f"{arm}: {path} missing (train the arm first)")
        df = pd.read_csv(path, dtype={"case_id": str})
        frames.append(df[df["split"] == "test"].assign(arm=arm))
    return pd.concat(frames, ignore_index=True)


# -------------------------------------------------------------------------------------- bootstrap
def encode(df: pd.DataFrame, classes: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    code = {c: i for i, c in enumerate(classes)}
    return (df["true_label"].map(code).to_numpy(), df["pred_label"].map(code).to_numpy(),
            df["confidence"].to_numpy(float))


def seed_draws(n_cases: dict[int, int], n_boot: int, seed: int) -> dict[int, np.ndarray]:
    """The same case resamples for every arm (paired), one (n_boot, n) index matrix per split seed."""
    rng = np.random.default_rng(seed)
    return {s: rng.integers(0, n, size=(n_boot, n)) for s, n in sorted(n_cases.items())}


def metrics_matrix(t, p, conf, k: int, draws: np.ndarray, bins: int) -> np.ndarray:
    """(n_boot, 4) macro-F1, balanced accuracy, accuracy, ECE over the resamples."""
    return np.array([_fast_metrics(t[i], p[i], conf[i], k, bins) for i in draws])


def summarise(preds: pd.DataFrame, arms: list[str], seeds: list[int], classes: list[str], n_boot: int,
              bins: int, boot_seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    k = len(classes)
    base = preds[(preds["missing_pct"] == 0.0)]
    # every arm must be tested on the same cases per seed, in the same order
    ref = {s: base[(base["arm"] == arms[0]) & (base["seed"] == s)].sort_values("case_id") for s in seeds}
    for arm, s in itertools.product(arms[1:], seeds):
        ids = base[(base["arm"] == arm) & (base["seed"] == s)]["case_id"].sort_values().to_numpy()
        if not np.array_equal(ids, ref[s]["case_id"].to_numpy()):
            raise ValueError(f"{arm} seed {s} was tested on different cases than {arms[0]}")
    draws = seed_draws({s: len(ref[s]) for s in seeds}, n_boot, boot_seed)

    def arm_arrays(arm: str, rate: float) -> dict:
        d = preds[(preds["arm"] == arm) & (preds["missing_pct"] == rate)]
        return {s: encode(d[d["seed"] == s].sort_values("case_id"), classes) for s in seeds}

    arrays = {arm: arm_arrays(arm, 0.0) for arm in arms}
    point, boot = {}, {}
    rows = []
    for arm in arms:
        point[arm] = np.array([_fast_metrics(*arrays[arm][s], k, bins) for s in seeds])          # (seeds, 4)
        boot[arm] = np.stack([metrics_matrix(*arrays[arm][s], k, draws[s], bins) for s in seeds])  # (seeds, B, 4)
        pooled = np.nanmean(boot[arm], axis=0)                                                    # (B, 4)
        for j, m in enumerate(FAST_NAMES):
            rows.append(_arm_row(arm, m, 0.0, point[arm][:, j], pooled[:, j], seeds))
        rates = sorted(preds.loc[preds["arm"] == arm, "missing_pct"].unique())
        if 1.0 in rates and rates != [0.0]:  # robustness: every answer hidden
            hid = arm_arrays(arm, 1.0)
            pt = np.array([_fast_metrics(*hid[s], k, bins)[0] for s in seeds])
            bt = np.nanmean(np.stack([metrics_matrix(*hid[s], k, draws[s], bins)[:, 0] for s in seeds]), axis=0)
            rows.append(_arm_row(arm, "macro_f1", 1.0, pt, bt, seeds))
    arm_table = pd.DataFrame(rows)

    pair_rows = []
    for a, b in pairs(arms):
        diff_pt = point[a][:, 0] - point[b][:, 0]
        diff_bt = boot[a][:, :, 0] - boot[b][:, :, 0]                                             # (seeds, B)
        row = {"row_type": "paired", "arm": a, "versus": b, "metric": "macro_f1", "missing_pct": 0.0,
               "n_seeds": len(seeds), "mean": diff_pt.mean(), "sd": diff_pt.std(ddof=1),
               "ci_low": np.nanquantile(diff_bt.mean(0), 0.025), "ci_high": np.nanquantile(diff_bt.mean(0), 0.975),
               "a_better_seeds": int((diff_pt > 0).sum()),
               "t_test_p": stats.ttest_rel(point[a][:, 0], point[b][:, 0]).pvalue if len(seeds) > 1 else np.nan,
               "wilcoxon_p": _wilcoxon(diff_pt)}
        for i, s in enumerate(seeds):
            row[f"seed{s}"] = diff_pt[i]
            row[f"seed{s}_ci"] = f"[{np.nanquantile(diff_bt[i], 0.025):.3f}, {np.nanquantile(diff_bt[i], 0.975):.3f}]"
        pair_rows.append(row)
    return arm_table, pd.DataFrame(pair_rows)


def _arm_row(arm, metric, rate, per_seed, pooled, seeds) -> dict:
    # ECE is biased upward under resampling: bias-corrected interval (see skinconcern.metrics)
    lo, hi = (bias_corrected_ci(per_seed.mean(), pooled) if metric == "ece"
              else (np.nanquantile(pooled, 0.025), np.nanquantile(pooled, 0.975)))
    row = {"row_type": "arm", "arm": arm, "versus": "", "metric": metric, "missing_pct": rate, "n_seeds": len(seeds),
           "mean": per_seed.mean(), "sd": per_seed.std(ddof=1) if len(seeds) > 1 else np.nan,
           "ci_low": lo, "ci_high": hi}
    row.update({f"seed{s}": v for s, v in zip(seeds, per_seed)})
    return row


def _wilcoxon(d: np.ndarray) -> float:
    if len(d) < 2 or np.allclose(d, 0):
        return np.nan
    return float(stats.wilcoxon(d).pvalue)


def pairs(arms: list[str]) -> list[tuple[str, str]]:
    """Every fusion arm against image-only and questionnaire-only, image vs questionnaire, and fusion
    variants against fusion_concat."""
    out = []
    fusion = [a for a in arms if a.startswith(("fusion_", "ensemble_", "stack_photo"))]
    for f in fusion:
        out += [(f, b) for b in ("image_only", "questionnaire_only") if b in arms]
    if {"image_only", "questionnaire_only"} <= set(arms):
        out.append(("image_only", "questionnaire_only"))
    if "fusion_concat" in arms:
        out += [(f, "fusion_concat") for f in fusion if f != "fusion_concat"]
    for a in ("stack_photo_q", "stack_photo_qmlp"):  # same photo predictions: isolates the questionnaire
        if {a, "stack_photo"} <= set(arms):
            out.append((a, "stack_photo"))
    return [(a, b) for a, b in out if a != b]



# --------------------------------------------------------------- skin tone and category (RQ1 "for whom", RQ3)
SCALES = {"eFST": (efst_group, ["I-II", "III-IV", "V-VI"]), "eMST": (emst_group, ["1-3", "4-6", "7-10"])}


def class_f1(t: np.ndarray, p: np.ndarray, k: int) -> np.ndarray:
    """F1 per class (NaN for a class absent from the true labels)."""
    cm = np.bincount(t * k + p, minlength=k * k).reshape(k, k)
    tp, denom = np.diag(cm).astype(float), (cm.sum(1) + cm.sum(0)).astype(float)
    return np.where(cm.sum(1) > 0, 2 * tp / np.maximum(denom, 1), np.nan)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (NaN entries are left out and stay NaN)."""
    p = np.asarray(pvalues, float)
    ok = np.where(~np.isnan(p))[0]
    adj = np.full(len(p), np.nan)
    running = 0.0
    for rank, i in enumerate(ok[np.argsort(p[ok])]):
        running = max(running, min(1.0, (len(ok) - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def subgroups(preds: pd.DataFrame, arms: list[str], seeds: list[int], classes: list[str], n_boot: int,
              boot_seed: int, reference: str = "image_only") -> pd.DataFrame:
    """Macro-F1 per skin-tone group and F1 per category for every arm, and paired differences vs ``reference``.

    Within a seed, the cases of a tone group are resampled inside the group, and categories use resamples
    of the whole test set; the resamples are shared by all arms (paired). Mean over seeds with a
    seed-stratified bootstrap CI, a t-test over seeds, and Holm-adjusted p within each comparison (all
    groups and categories of one arm vs the reference form one family).
    """
    k = len(classes)
    code = {c: i for i, c in enumerate(classes)}
    base = preds[preds["missing_pct"] == 0.0].copy()
    for scale, (fn, _) in SCALES.items():
        base[f"{scale}_group"] = base[scale].map(fn)
    per = {(a, s): base[(base["arm"] == a) & (base["seed"] == s)].sort_values("case_id").reset_index(drop=True)
           for a in arms for s in seeds}
    units = [(scale, g) for scale, (_, gs) in SCALES.items() for g in gs] + [("class", c) for c in classes]
    rng = np.random.default_rng(boot_seed + 1)
    point, boot, n_cases = {}, {}, {}
    for s in seeds:
        ref = per[(arms[0], s)]
        whole = rng.integers(0, len(ref), size=(n_boot, len(ref)))
        groups = {}
        for scale, (_, gs) in SCALES.items():
            for g in gs:
                rows = np.where(ref[f"{scale}_group"].to_numpy() == g)[0]
                draws = rows[rng.integers(0, len(rows), size=(n_boot, len(rows)))] if len(rows) else None
                groups[(scale, g)] = (rows, draws)
                n_cases.setdefault((scale, g), []).append(len(rows))
        tt_ref = ref["true_label"].map(code).to_numpy()
        for j, c in enumerate(classes):
            n_cases.setdefault(("class", c), []).append(int((tt_ref == j).sum()))
        for a in arms:
            d = per[(a, s)]
            tt, pp = d["true_label"].map(code).to_numpy(), d["pred_label"].map(code).to_numpy()
            conf = d["confidence"].to_numpy(float)
            for u, (rows, draws) in groups.items():
                if len(rows) < 2:
                    v, b = np.nan, np.full(n_boot, np.nan)
                else:
                    v = _fast_metrics(tt[rows], pp[rows], conf[rows], k, 15)[0]
                    b = np.array([_fast_metrics(tt[i], pp[i], conf[i], k, 15)[0] for i in draws])
                point.setdefault((a, u), []).append(v)
                boot.setdefault((a, u), []).append(b)
            f1, fb = class_f1(tt, pp, k), np.array([class_f1(tt[i], pp[i], k) for i in whole])
            for j, c in enumerate(classes):
                point.setdefault((a, ("class", c)), []).append(f1[j])
                boot.setdefault((a, ("class", c)), []).append(fb[:, j])

    def kind(u, prefix):
        return f"{prefix}_class" if u[0] == "class" else f"{prefix}_group"

    rows = []
    for a in arms:
        for u in units:
            pt, bt = np.array(point[(a, u)]), np.nanmean(np.stack(boot[(a, u)]), axis=0)
            rows.append({"row_type": kind(u, "arm"), "arm": a, "versus": "", "scale": u[0], "group": u[1],
                         "metric": "f1" if u[0] == "class" else "macro_f1", "missing_pct": 0.0,
                         "n_seeds": int(np.sum(~np.isnan(pt))), "mean_n_cases": float(np.mean(n_cases[u])),
                         "mean": np.nanmean(pt), "sd": np.nanstd(pt, ddof=1),
                         "ci_low": np.nanquantile(bt, 0.025), "ci_high": np.nanquantile(bt, 0.975)})
    if reference in arms:
        for a in [x for x in arms if x != reference]:
            fam = []
            for u in units:
                d_pt = np.array(point[(a, u)]) - np.array(point[(reference, u)])
                d_bt = np.nanmean(np.stack(boot[(a, u)]) - np.stack(boot[(reference, u)]), axis=0)
                ok = ~np.isnan(d_pt)
                tp = (stats.ttest_1samp(d_pt[ok], 0).pvalue
                      if ok.sum() > 1 and np.std(d_pt[ok]) > 0 else np.nan)
                fam.append({"row_type": kind(u, "paired"), "arm": a, "versus": reference, "scale": u[0],
                            "group": u[1], "metric": "f1" if u[0] == "class" else "macro_f1", "missing_pct": 0.0,
                            "n_seeds": int(ok.sum()), "mean_n_cases": float(np.mean(n_cases[u])),
                            "mean": np.nanmean(d_pt), "sd": np.nanstd(d_pt, ddof=1),
                            "ci_low": np.nanquantile(d_bt, 0.025), "ci_high": np.nanquantile(d_bt, 0.975),
                            "a_better_seeds": int((d_pt[ok] > 0).sum()), "t_test_p": tp})
            for r, h in zip(fam, holm([r["t_test_p"] for r in fam])):
                r["holm_p"] = h
            rows += fam
    return pd.DataFrame(rows)


def markdown_subgroups(sub: pd.DataFrame, arms: list[str], reference: str = "image_only") -> str:
    units = list(dict.fromkeys(zip(sub["scale"], sub["group"])))
    head = [g if s == "class" else f"{s} {g}" for s, g in units]
    arm_rows = sub[sub["row_type"].isin(["arm_group", "arm_class"])]
    n = arm_rows[arm_rows["arm"] == arms[0]].set_index(["scale", "group"])["mean_n_cases"]
    lines = ["", "## By skin tone (macro-F1) and by category (F1)", "",
             "Mean ± sd over seeds. Mean test cases per seed: "
             + ", ".join(f"{h} {n[u]:.0f}" for h, u in zip(head, units)) + ".", "",
             "| Arm | " + " | ".join(head) + " |", "|---|" + "---|" * len(units)]
    for a in arms:
        r = arm_rows[arm_rows["arm"] == a].set_index(["scale", "group"])
        lines.append(f"| {a} | " + " | ".join(f"{r.loc[u, 'mean']:.3f} ± {r.loc[u, 'sd']:.3f}" for u in units) + " |")
    pair_rows = sub[sub["row_type"].isin(["paired_group", "paired_class"])]
    if len(pair_rows):
        lines += ["", f"Difference vs {reference}: mean [95% seed-stratified paired bootstrap CI], seeds better; "
                  "Holm-adjusted p shown when < 0.05 (family = all groups and categories of one comparison).", "",
                  "| Arm | " + " | ".join(head) + " |", "|---|" + "---|" * len(units)]
        for a in [x for x in arms if x != reference]:
            r = pair_rows[pair_rows["arm"] == a].set_index(["scale", "group"])
            cells = []
            for u in units:
                x = r.loc[u]
                star = f" **p={x['holm_p']:.3f}**" if x["holm_p"] < 0.05 else ""
                cells.append(f"{x['mean']:+.3f} [{x['ci_low']:+.3f}, {x['ci_high']:+.3f}] "
                             f"{int(x['a_better_seeds'])}/{int(x['n_seeds'])}{star}")
            lines.append(f"| {a} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"

# ------------------------------------------------------------------------------------------ table
def markdown(arm_table: pd.DataFrame, pair_table: pd.DataFrame, meta: dict) -> str:
    def cell(r):
        return f"{r['mean']:.3f} ± {r['sd']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]"

    lines = [f"# E1: photo only vs questionnaire only vs fusion (test, seeds {meta['seeds']})", "",
             f"Backbone {meta['backbone']}, imbalance correction {meta['balance']}. Each cell: mean ± sd over seeds "
             "[95% seed-stratified case-bootstrap CI].", "",
             "| Arm | Macro-F1 | Balanced accuracy | ECE | Macro-F1, all answers hidden |", "|---|---|---|---|---|"]
    for arm in meta["arms"]:
        a = arm_table[arm_table["arm"] == arm]
        get = lambda m, r=0.0: a[(a["metric"] == m) & (a["missing_pct"] == r)]  # noqa: E731
        hid = get("macro_f1", 1.0)
        lines.append(f"| {arm} | {cell(get('macro_f1').iloc[0])} | {cell(get('balanced_acc').iloc[0])} | "
                     f"{cell(get('ece').iloc[0])} | {cell(hid.iloc[0]) if len(hid) else 'n/a'} |")
    seeds = meta["seeds"]
    lines += ["", "Paired macro-F1 difference A - B on the shared test cases (per seed, mean with seed-stratified "
              "paired bootstrap CI, seeds where A is better, paired t-test and Wilcoxon p over seeds).", "",
              "| A | B | " + " | ".join(f"seed {s}" for s in seeds) + " | Mean [95% CI] | A better | t p | Wilcoxon p |",
              "|---|---|" + "---|" * len(seeds) + "---|---|---|---|"]
    for _, r in pair_table.iterrows():
        lines.append(f"| {r['arm']} | {r['versus']} | " + " | ".join(f"{r[f'seed{s}']:+.3f}" for s in seeds)
                     + f" | {r['mean']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}] | {r['a_better_seeds']}/"
                     f"{len(seeds)} | {r['t_test_p']:.3f} | {r['wilcoxon_p']:.3f} |")
    lines += ["", "The CI reflects test-set sampling (cases); the sd reflects training randomness (seeds). The ECE "
              "interval is bias-corrected (ECE is biased upward under resampling). With 5 seeds the Wilcoxon test "
              "cannot go below p = 0.0625."]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", nargs="+", default=DEFAULT_ARMS)
    ap.add_argument("--backbone", choices=BACKBONES, default="efficientnet_b0")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--no-train", action="store_true", help="only build the tables from existing runs")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--bins", type=int, default=15, help="ECE bins (as evaluate.py)")
    ap.add_argument("--boot-seed", type=int, default=0)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e1")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    specs = {arm: arm_spec(arm, args.backbone, args.balance) for arm in args.arms}
    if not args.no_train:
        for arm, spec in specs.items():
            log.info("=== %s (%s)", arm, spec["dir"])
            spec["train"]({"balance": args.balance, "seeds": args.seeds, "skip_existing": True})
    preds = pd.concat([load_predictions(a, s, args.seeds) for a, s in specs.items()], ignore_index=True)
    classes = sorted(set(preds["true_label"]) | set(preds["pred_label"]))
    arm_table, pair_table = summarise(preds, args.arms, args.seeds, classes, args.n_boot, args.bins, args.boot_seed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    meta = {"arms": args.arms, "seeds": args.seeds, "backbone": args.backbone, "balance": args.balance}
    sub = subgroups(preds, args.arms, args.seeds, classes, args.n_boot, args.boot_seed)
    summary = pd.concat([arm_table, pair_table, sub], ignore_index=True)
    summary.insert(0, "backbone", args.backbone)
    summary.insert(1, "balance", args.balance)
    summary.to_csv(args.out_dir / "e1_summary.csv", index=False, float_format="%.5f")
    text = markdown(arm_table, pair_table, meta) + markdown_subgroups(sub, args.arms)
    (args.out_dir / "e1_table.md").write_text(text, encoding="utf-8")
    log.info("wrote %s and e1_table.md", args.out_dir / "e1_summary.csv")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
