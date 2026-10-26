"""E3 / Task 4.1 (RQ3): one skin-tone table for every main model, from the stored test predictions.

Nothing is retrained. For each arm and seed the SCIN test cases are split by eFST and eMST group and
scored (macro-F1, balanced accuracy); the seeds are summarised as mean +- sd with a 95% interval from
a case bootstrap inside each group and seed (the same resamples for every arm, so differences are
paired). Reported per tone group:

  arm           macro-F1 / balanced accuracy of the model
  delta         paired difference vs the photo-only EfficientNet-B0 (what the questionnaire, a frozen
                foundation encoder or extra atlas training data adds for that group); t-test over seeds,
                Holm within each arm (all groups of both scales form one family)
  missing_drop  macro-F1 with every questionnaire answer hidden minus with the answers (E2, r = 1 vs 0)
  gap           best minus worst group per seed (groups with >= 20 test cases in that seed only)
Groups with fewer than 30 test cases per seed on average are flagged ``small`` (descriptive only).
Second dataset: Fitzpatrick17k zero-shot (every in-scope image, the same images for every seed; the
interval resamples whole images) for the photo-only and DINOv2 app models.

Outputs in ``results/e3/``: e3_by_tone.csv, e3_table.md, e3_benefit_by_tone.png.

Usage::

    python analyze_fairness.py
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
from run_e1 import arm_spec, holm, load_predictions  # noqa: E402
from skinconcern.metrics import _fast_metrics, efst_group, emst_group  # noqa: E402

log = logging.getLogger("analyze_fairness")
CLASSES = ["acne", "eczema_dermatitis", "redness_rosacea", "normal_other"]
REFERENCE = "image_only"
SCIN_ARMS = ["image_only", "questionnaire_only", "fusion_concat", "fusion_film", "fusion_gated",
             "probe_dinov2", "probe_dermlip", "probe_panderm_large", "fitz_pooled"]
MISSING_ARMS = ["fusion_concat_nodrop", "fusion_concat", "fusion_concat_randdrop", "fusion_film"]
FITZ_ARMS = ["image_only", "probe_dinov2"]
LABEL = {"image_only": "Photo, EfficientNet-B0", "questionnaire_only": "Questionnaire only",
         "fusion_concat": "Fusion concat (answer dropout)", "fusion_concat_nodrop": "Fusion concat (no dropout)",
         "fusion_concat_randdrop": "Fusion concat (random dropout)", "fusion_film": "Fusion FiLM",
         "fusion_gated": "Fusion gated", "probe_dinov2": "DINOv2 + probe (app model)",
         "probe_dermlip": "DermLIP + probe", "probe_panderm_large": "PanDerm-Large + probe",
         "fitz_pooled": "Photo, trained on SCIN + Fitzpatrick17k (E7)"}
SCALES = {"eFST": (efst_group, ["I-II", "III-IV", "V-VI"]), "eMST": (emst_group, ["1-3", "4-6", "7-10"])}
METRICS = {"macro_f1": 0, "balanced_acc": 1}
MIN_GAP_N, SMALL_N = 20, 30


# ---------------------------------------------------------------------------------------- loading
def scin_predictions(arm: str, seeds: list[int], missing_pct: float = 0.0) -> dict[int, pd.DataFrame]:
    """Test predictions per seed, sorted by case, at one share of hidden answers."""
    if arm == "fitz_pooled":
        d = ROOT / "runs" / "e7_fitzpatrick" / "efficientnet_b0_fitz_pooled"
        df = pd.concat([pd.read_csv(d / f"seed{s}" / "predictions.csv", dtype={"case_id": str}) for s in seeds])
        df = df[df["split"] == "test"]
    else:
        df = load_predictions(arm, arm_spec(arm, "efficientnet_b0", "weighted_loss"), seeds)
    df = df[np.isclose(df["missing_pct"], missing_pct)]
    if df.empty:
        raise ValueError(f"{arm}: no test predictions with missing_pct = {missing_pct}")
    return {s: d.sort_values("case_id").reset_index(drop=True) for s, d in df.groupby("seed")}


def fitz_predictions(arm: str, seeds: list[int]) -> dict[int, pd.DataFrame]:
    """Zero-shot Fitzpatrick17k predictions of every in-scope image (cached by run_e4.py)."""
    df = pd.read_csv(ROOT / "runs" / "external_eval" / "e4" / f"{arm}_fitzpatrick17k.csv", dtype={"case_id": str})
    df = df[df["true_label"].isin(CLASSES) & df["seed"].isin(seeds)]
    probs = df[[f"prob_{c}" for c in CLASSES]].to_numpy(float)
    df = df.assign(pred_label=np.array(CLASSES)[probs.argmax(1)], confidence=probs.max(1), eMST=pd.NA)
    return {s: d.sort_values("case_id").reset_index(drop=True) for s, d in df.groupby("seed")}


# ------------------------------------------------------------------------------------------ core
def tone_scores(frames: dict[str, dict[int, pd.DataFrame]], seeds: list[int], n_boot: int, seed: int = 0,
                shared_cases: bool = False) -> tuple[dict, dict, dict]:
    """Point values and bootstrap draws of each metric per (arm, scale, group, seed).

    The resamples of a group are drawn once per seed and used for every arm (paired). With
    ``shared_cases`` (an external set scored by every seed's model) one set of image resamples is used
    for all seeds, so the interval reflects the images, not ten copies of them.
    """
    rng = np.random.default_rng(seed)
    code = {c: i for i, c in enumerate(CLASSES)}
    ref_arm = next(iter(frames))
    point, boot, n = {}, {}, {}
    fixed_draws = {}
    for s in seeds:
        ref = frames[ref_arm][s]
        for a, fr in frames.items():
            if not fr[s]["case_id"].equals(ref["case_id"]):
                raise ValueError(f"{a} seed {s}: test cases differ from {ref_arm}")
        for scale, (fn, groups) in SCALES.items():
            tone = ref[scale].map(fn).to_numpy()
            for g in groups:
                rows = np.flatnonzero(tone == g)
                n.setdefault((scale, g), []).append(len(rows))
                if shared_cases:
                    draws = fixed_draws.setdefault((scale, g), rows[rng.integers(0, len(rows), (n_boot, len(rows)))]
                                                   if len(rows) else None)
                else:
                    draws = rows[rng.integers(0, len(rows), (n_boot, len(rows)))] if len(rows) else None
                for a, fr in frames.items():
                    d = fr[s]
                    t, p = d["true_label"].map(code).to_numpy(), d["pred_label"].map(code).to_numpy()
                    c = d["confidence"].to_numpy(float)
                    if len(rows) < 2:
                        v, b = np.full(2, np.nan), np.full((n_boot, 2), np.nan)
                    else:
                        v = np.array(_fast_metrics(t[rows], p[rows], c[rows], len(CLASSES), 15)[:2])
                        b = np.array([_fast_metrics(t[i], p[i], c[i], len(CLASSES), 15)[:2] for i in draws])
                    point.setdefault((a, scale, g), []).append(v)
                    boot.setdefault((a, scale, g), []).append(b)
    point = {k: np.stack(v) for k, v in point.items()}   # (seeds, metrics)
    boot = {k: np.stack(v) for k, v in boot.items()}     # (seeds, n_boot, metrics)
    return point, boot, {k: np.array(v) for k, v in n.items()}


def _row(kind, dataset, arm, versus, scale, group, metric, pt, bt, n_cases, **extra) -> dict:
    """``pt``: one value per seed; ``bt``: (seeds, n_boot) resampled values, averaged over seeds per resample."""
    ok = ~np.isnan(pt)
    seed_mean = np.nanmean(bt, axis=0)
    return {"dataset": dataset, "kind": kind, "arm": arm, "versus": versus, "scale": scale, "group": group,
            "metric": metric, "n_seeds": int(ok.sum()), "mean": np.nanmean(pt) if ok.any() else np.nan,
            "sd": np.nanstd(pt, ddof=1) if ok.sum() > 1 else np.nan,
            "ci_low": np.nanquantile(seed_mean, 0.025) if np.isfinite(seed_mean).any() else np.nan,
            "ci_high": np.nanquantile(seed_mean, 0.975) if np.isfinite(seed_mean).any() else np.nan,
            "mean_n_cases": float(np.mean(n_cases)), "small": bool(np.mean(n_cases) < SMALL_N), **extra}


def _test(d: np.ndarray) -> dict:
    ok = ~np.isnan(d)
    p = stats.ttest_1samp(d[ok], 0).pvalue if ok.sum() > 1 and np.std(d[ok]) > 0 else np.nan
    return {"better_seeds": int((d[ok] > 0).sum()), "t_test_p": p}


def summarise(dataset: str, point: dict, boot: dict, n: dict, arms: list[str],
              contrasts: list[tuple[str, str, str]]) -> list[dict]:
    """Rows for every arm and group, every contrast (kind, a, b) as a - b per group, and the gaps."""
    rows = []
    for a in arms:
        for scale, (_, groups) in SCALES.items():
            for g in groups:
                for m, j in METRICS.items():
                    rows.append(_row("arm", dataset, a, "", scale, g, m, point[(a, scale, g)][:, j],
                                     boot[(a, scale, g)][:, :, j], n[(scale, g)]))
            # gap: best minus worst group per seed (and per resample), among groups large enough in that seed
            big = np.stack([n[(scale, g)] >= MIN_GAP_N for g in groups], 1)                    # (seeds, groups)
            f1 = np.stack([point[(a, scale, g)][:, 0] for g in groups], 1)
            f1 = np.where(big, f1, np.nan)
            gap_pt = np.nanmax(f1, 1) - np.nanmin(f1, 1)
            if np.isnan(f1).all():  # no tone labels on this scale (e.g. eMST on Fitzpatrick17k)
                continue
            worst = groups[int(np.nanargmin(np.nanmean(f1, 0)))]
            # no bootstrap interval: the range of noisy group estimates is biased upwards, so the gap is
            # given as mean +- sd over seeds and is meant for comparing models, not as an absolute value
            rows.append(_row("gap", dataset, a, "", scale, f"worst {worst}", "macro_f1", gap_pt,
                             np.full((len(gap_pt), 1), np.nan), np.array([0]), small=False))
    for kind, a, b in contrasts:
        fam = []
        for scale, (_, groups) in SCALES.items():
            for g in groups:
                d_pt = point[(a, scale, g)][:, 0] - point[(b, scale, g)][:, 0]
                d_bt = boot[(a, scale, g)][:, :, 0] - boot[(b, scale, g)][:, :, 0]
                fam.append(_row(kind, dataset, a.split("@")[0], b, scale, g, "macro_f1", d_pt, d_bt,
                                n[(scale, g)], **_test(d_pt)))
        for r, h in zip(fam, holm([r["t_test_p"] for r in fam])):
            r["holm_p"] = h
        rows += fam
    return rows


# --------------------------------------------------------------------------------------- outputs
def fmt(r) -> str:
    if pd.isna(r["mean"]):
        return "n/a"
    small = " (s)" if r["small"] else ""
    if r["kind"] == "arm":
        return f"{r['mean']:.3f} ± {r['sd']:.3f}{small}"
    star = "*" if r.get("holm_p", 1) < 0.05 else ""
    return f"{r['mean']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]{star}{small}"


def markdown(res: pd.DataFrame, seeds) -> str:
    def table(df, arms, kind, scales=("eFST", "eMST"), metric="macro_f1", title=""):
        out = [f"## {title}", ""]
        show_gap = kind == "arm" and metric == "macro_f1"
        for scale in scales:
            groups = SCALES[scale][1]
            n = df[(df.scale == scale) & (df.kind == "arm") & (df.metric == "macro_f1")].drop_duplicates("group") \
                .set_index("group")["mean_n_cases"]
            out += [f"| Model | " + " | ".join(f"{scale} {g} (n={n.get(g, 0):.0f})" for g in groups)
                    + (" | gap (worst group) |" if show_gap else " |"),
                    "|---" * (len(groups) + 1 + show_gap) + "|"]
            for a in arms:
                sel = df[(df.arm == a) & (df.kind == kind) & (df.scale == scale) & (df.metric == metric)]
                if sel.empty:
                    continue
                cells = [fmt(sel[sel.group == g].iloc[0]) for g in groups]
                if show_gap:
                    gp = df[(df.arm == a) & (df.kind == "gap") & (df.scale == scale)].iloc[0]
                    cells.append(f"{gp['mean']:.3f} ± {gp['sd']:.3f} ({gp['group']})")
                out.append(f"| {LABEL[a]} | " + " | ".join(cells) + " |")
            out.append("")
        return out

    scin, fitz = res[res.dataset == "scin"], res[res.dataset == "fitzpatrick17k"]
    out = ["# E3 (Task 4.1, RQ3): results by skin tone", "",
           f"Seeds {seeds}, stored test predictions (nothing retrained). Mean ± sd over seeds for a model; for "
           "differences the mean over seeds with a 95% paired bootstrap interval (cases resampled inside each group "
           "and seed). * = Holm-adjusted p < 0.05 within the model's family (all groups of both scales). "
           f"(s) = fewer than {SMALL_N} test cases per seed: descriptive only. n = mean test cases per seed. "
           f"Gap = best minus worst macro-F1 group per seed, over groups with at least {MIN_GAP_N} cases (mean ± sd; "
           "noise in small groups inflates it, so compare it between models).", ""]
    out += table(scin, SCIN_ARMS, "arm", title="SCIN test: macro-F1 by tone group")
    out += table(scin, SCIN_ARMS, "arm", metric="balanced_acc", title="SCIN test: balanced accuracy by tone group")
    out += table(scin, [a for a in SCIN_ARMS if a != REFERENCE], "delta",
                 title="SCIN test: macro-F1 difference vs the photo-only model")
    out += table(scin, MISSING_ARMS, "missing_drop",
                 title="SCIN test: macro-F1 with every answer hidden minus with the answers (E2, r = 1 vs 0)")
    out += table(fitz, FITZ_ARMS, "arm", scales=("eFST",),
                 title="Fitzpatrick17k zero-shot (every in-scope image, same images for every seed): macro-F1")
    out += table(fitz, ["probe_dinov2"], "delta", scales=("eFST",),
                 title="Fitzpatrick17k zero-shot: DINOv2 + probe minus photo-only")
    return "\n".join(out) + "\n"


def plot(res: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = [("delta", "fusion_concat", "Fusion concat - photo", "#8e44ad"),
              ("delta", "fusion_film", "Fusion FiLM - photo", "#c39bd3"),
              ("missing_drop", "fusion_concat_nodrop", "Answers hidden - shown (concat, no dropout)", "#b9770e"),
              ("delta", "probe_dinov2", "DINOv2 probe - photo", "#2471a3"),
              ("delta", "fitz_pooled", "SCIN + Fitzpatrick17k training - photo", "#7f8c8d")]
    scin = res[res.dataset == "scin"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9), sharey=True)
    w = 0.8 / len(series)
    for ax, (scale, (_, groups)) in zip(axes, SCALES.items()):
        for i, (kind, arm, label, color) in enumerate(series):
            d = scin[(scin.kind == kind) & (scin.arm == arm) & (scin.scale == scale)].set_index("group").loc[groups]
            x = np.arange(len(groups)) + (i - (len(series) - 1) / 2) * w
            ax.bar(x, d["mean"], w, color=color, label=label,
                   yerr=[d["mean"] - d["ci_low"], d["ci_high"] - d["mean"]], capsize=2, error_kw={"elinewidth": 0.7})
        n = scin[(scin.kind == "arm") & (scin.scale == scale)].drop_duplicates("group").set_index("group")["mean_n_cases"]
        ax.set_xticks(np.arange(len(groups)))
        ax.set_xticklabels([f"{scale} {g}\n(n={n[g]:.0f}{', small' if n[g] < SMALL_N else ''})" for g in groups],
                           fontsize=8)
        ax.axhline(0, color="black", lw=0.7)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("macro-F1 difference (SCIN test)")
    axes[0].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e3")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    frames = {a: scin_predictions(a, args.seeds) for a in SCIN_ARMS}
    for a in MISSING_ARMS:
        frames[f"{a}@r0"] = scin_predictions(a, args.seeds, 0.0)
        frames[f"{a}@r1"] = scin_predictions(a, args.seeds, 1.0)
    point, boot, n = tone_scores(frames, args.seeds, args.n_boot)
    contrasts = [("delta", a, REFERENCE) for a in SCIN_ARMS if a != REFERENCE]
    contrasts += [("missing_drop", f"{a}@r1", f"{a}@r0") for a in MISSING_ARMS]
    rows = summarise("scin", point, boot, n, SCIN_ARMS, contrasts)
    log.info("SCIN done (%d arms)", len(frames))

    fitz = {a: fitz_predictions(a, args.seeds) for a in FITZ_ARMS}
    point, boot, n = tone_scores(fitz, args.seeds, args.n_boot, seed=1, shared_cases=True)
    rows += [r for r in summarise("fitzpatrick17k", point, boot, n, FITZ_ARMS, [("delta", "probe_dinov2", REFERENCE)])
             if r["scale"] == "eFST"]
    res = pd.DataFrame(rows)
    res.to_csv(args.out_dir / "e3_by_tone.csv", index=False)
    (args.out_dir / "e3_table.md").write_text(markdown(res, args.seeds), encoding="utf-8")
    plot(res, args.out_dir / "e3_benefit_by_tone.png")
    log.info("wrote %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
