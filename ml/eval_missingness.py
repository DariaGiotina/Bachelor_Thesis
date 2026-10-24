"""E2 / Task 3.5: missing-answer robustness by field, on naturally missing questionnaires, and as a curve.

Completes E2 (``run_e2_dropout.py`` covers the random removal of a share r of the answers). Three
analyses, all on the SCIN test split of every split seed, with the trained fusion checkpoints:

1. Field-wise removal (needs the checkpoints and the test images). For every questionnaire field
   (age group, body area, symptoms, texture, duration, skin type) two conditions are scored:
     hide:<field>   that field is hidden for every test case (all other answers kept)
     only:<field>   every other field is hidden (only this answer kept)
   plus ``none`` (no answer hidden) and ``all`` (whole questionnaire hidden). A hidden field gets
   feature 0 and mask 1, exactly like a skipped answer (no imputation). The change against ``none``
   is paired per seed: mean, t-based 95% CI over seeds, number of seeds where it is negative, and the
   t-test p-value, Holm-adjusted over the fields of one arm and one condition type.
2. Naturally missing subgroup (from the existing predictions, no inference). Test cases are grouped
   by how many of the 6 fields the contributor left unanswered in SCIN: ``complete`` (0), ``partial``
   (1-5) and ``empty`` (6). For each group: macro-F1 of each fusion arm and of the photo-only model on
   the same cases, and the paired fusion-minus-photo difference.
3. Curve (from the existing predictions): macro-F1 against the share r of answers hidden at random
   (0, 25, 50, 75, 100%), mean and t-based 95% CI over seeds, one line per arm, photo-only as the floor.

Arms: ``fusion_concat_nodrop`` (no hidden answers in training), ``fusion_concat`` (fixed rates, E1),
``fusion_concat_randdrop`` (rate sampled per batch), ``fusion_film`` (best fusion variant in E1), and
``image_only`` (reference; it never reads the questionnaire).

Outputs in ``results/e2/``: ``e2_missingness_results.csv`` (one row per arm x condition x seed),
``e2_missingness_table.md`` and ``e2_curve.png``.

Usage::

    python eval_missingness.py                     # all arms, seeds 0-9
    python eval_missingness.py --no-fieldwise      # only the analyses that need no inference
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from data_loading import ROOT, get_dataloaders  # noqa: E402
from dropout_utils import field_index  # noqa: E402
from run_e1 import arm_spec, holm, load_predictions  # noqa: E402
from skinconcern.metrics import macro_f1  # noqa: E402
from train import build_fusion  # noqa: E402

log = logging.getLogger("eval_missingness")
FUSION_ARMS = ["fusion_concat_nodrop", "fusion_concat", "fusion_concat_randdrop", "fusion_film"]
LABEL = {"fusion_concat_nodrop": "concat, no dropout", "fusion_concat": "concat, fixed dropout",
         "fusion_concat_randdrop": "concat, random dropout", "fusion_film": "FiLM, fixed dropout",
         "image_only": "photo only"}
NATURAL_GROUPS = ("complete", "partial", "empty")
MIN_GROUP = 30  # smaller groups are flagged in the table


# ------------------------------------------------------------------------------------ helpers
def checkpoint(arm_dir: Path, seed: int) -> Path:
    hits = sorted((arm_dir / "seed_checkpoints").glob(f"*_seed{seed}.pt"))
    if len(hits) != 1:
        raise FileNotFoundError(f"expected one checkpoint for seed {seed} in {arm_dir}, found {hits}")
    return hits[0]


def hide(q_vec: torch.Tensor, q_mask: torch.Tensor, fields: list[torch.Tensor], drop: list[int]):
    """Hide the fields in ``drop`` for every case: features 0, mask 1 (never imputes)."""
    q_vec, q_mask = q_vec.clone(), q_mask.clone()
    for j in drop:
        q_vec[:, fields[j]] = 0.0
        q_mask[:, j] = 1.0
    return q_vec, q_mask


def conditions(field_names: list[str]) -> dict[str, list[int]]:
    """Condition name -> indices of the fields hidden in it."""
    k = len(field_names)
    out = {"none": [], "all": list(range(k))}
    for j, f in enumerate(field_names):
        out[f"hide:{f}"] = [j]
        out[f"only:{f}"] = [i for i in range(k) if i != j]
    return out


def ci_t(x: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    x = np.asarray(x, float)
    if len(x) < 2:
        return float("nan"), float("nan")
    h = stats.t.ppf(1 - alpha / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean() - h), float(x.mean() + h)


def paired(a: np.ndarray, b: np.ndarray) -> dict:
    """a - b over seeds: mean, 95% t CI, seeds with a < b, paired t-test p."""
    d = np.asarray(a, float) - np.asarray(b, float)
    lo, hi = ci_t(d)
    p = float(stats.ttest_1samp(d, 0.0).pvalue) if len(d) > 1 and d.std() > 0 else 1.0
    return {"delta": float(d.mean()), "ci_low": lo, "ci_high": hi, "n_neg": int((d < 0).sum()), "n": len(d), "p": p}


# ------------------------------------------------------------------------ 1. field-wise removal
@torch.no_grad()
def fieldwise(seeds: list[int], backbone: str, balance: str, device: torch.device) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        cache = None
        for arm in FUSION_ARMS:
            arm_dir = arm_spec(arm, backbone, balance)["dir"]
            cfg = yaml.safe_load((arm_dir / "config_used.yaml").read_text(encoding="utf-8"))
            cfg["loader"]["num_workers"] = 0
            if cache is None:  # the test images are the same for every arm of a seed: load them once
                loader = get_dataloaders(cfg, seed, split="test")
                ds = loader.dataset
                batches = list(loader)
                cache = {
                    "image": torch.cat([b["image"] for b in batches]).half(),
                    "q_vec": torch.cat([b["q_vec"] for b in batches]).float(),
                    "q_mask": torch.cat([b["q_mask"] for b in batches]).float(),
                    "label": torch.cat([b["label"] for b in batches]).numpy(),
                    "classes": ds.classes, "fields": field_index(ds.q_cols, ds.m_cols),
                    "names": [m.split("__", 1)[1] for m in ds.m_cols],
                    "dims": (len(ds.q_cols), len(ds.m_cols)),
                }
            model = build_fusion(cfg, len(cache["classes"]), *cache["dims"]).to(device)
            model.load_state_dict(torch.load(checkpoint(arm_dir, seed), map_location=device, weights_only=True))
            model.eval()
            for cond, drop in conditions(cache["names"]).items():
                q_vec, q_mask = hide(cache["q_vec"], cache["q_mask"], cache["fields"], drop)
                preds = []
                for i in range(0, len(q_vec), 128):
                    with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                        logits = model(image=cache["image"][i:i + 128].to(device).float(),
                                       q_vec=q_vec[i:i + 128].to(device), q_mask=q_mask[i:i + 128].to(device))
                    preds.append(logits.float().argmax(1).cpu().numpy())
                pred = np.concatenate(preds)
                rows.append({"analysis": "fieldwise", "arm": arm, "condition": cond, "seed": seed,
                             "n": len(pred), "macro_f1": macro_f1(cache["label"], pred)})
            done = {r["condition"]: r["macro_f1"] for r in rows if r["arm"] == arm and r["seed"] == seed}
            log.info("seed %d %s: none %.3f, all hidden %.3f", seed, arm, done["none"], done["all"])
            del model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return pd.DataFrame(rows)


# ----------------------------------------------------------------- 2. naturally missing subgroup
def natural_groups() -> pd.Series:
    q = pd.read_parquet(ROOT / "features" / "questionnaire_features.parquet")
    masks = q[[c for c in q.columns if c.startswith("m__")]]
    # count only fields that are really skipped: age is missing for 1 of 5,033 cases, because
    # "age unknown" is an explicit answer, so it would make "empty" impossible
    masks = masks.loc[:, masks.mean(axis=0) > 0.01]
    n_missing, k = masks.sum(axis=1), masks.shape[1]
    grp = np.where(n_missing == 0, "complete", np.where(n_missing == k, "empty", "partial"))
    return pd.Series(grp, index=q.index.astype(str), name="natural")


def natural(preds: pd.DataFrame, seeds: list[int]) -> pd.DataFrame:
    grp = natural_groups()
    p = preds[preds["missing_pct"] == 0.0].copy()
    p["natural"] = p["case_id"].map(grp)
    rows = []
    for (arm, seed, g), d in p.groupby(["arm", "seed", "natural"]):
        rows.append({"analysis": "natural", "arm": arm, "condition": g, "seed": seed, "n": len(d),
                     "macro_f1": macro_f1(d["true_label"], d["pred_label"])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- 3. random-rate curve
def curve(preds: pd.DataFrame, rates: list[float]) -> pd.DataFrame:
    rows = []
    for (arm, seed, r), d in preds.groupby(["arm", "seed", "missing_pct"]):
        rows.append({"analysis": "random", "arm": arm, "condition": f"r={r:g}", "seed": seed, "n": len(d),
                     "macro_f1": macro_f1(d["true_label"], d["pred_label"])})
    img = [x for x in rows if x["arm"] == "image_only"]
    for x in img:  # the photo-only model is the same at every rate
        rows += [{**x, "condition": f"r={r:g}"} for r in rates if r != 0.0]
    return pd.DataFrame(rows)


def plot_curve(res: pd.DataFrame, rates: list[float], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    styles = {"image_only": dict(color="black", ls="--"), "fusion_concat_nodrop": dict(color="#c0392b"),
              "fusion_concat": dict(color="#2471a3"), "fusion_concat_randdrop": dict(color="#229954"),
              "fusion_film": dict(color="#8e44ad")}
    d = res[res["analysis"] == "random"]
    for i, (arm, st) in enumerate(styles.items()):
        a = d[d["arm"] == arm]
        if a.empty:
            continue
        m, err = [], [[], []]
        for r in rates:
            x = a[a["condition"] == f"r={r:g}"].sort_values("seed")["macro_f1"].to_numpy()
            l, h = ci_t(x)
            m.append(x.mean())
            err[0].append(x.mean() - l)
            err[1].append(h - x.mean())
        xs = [100 * r + (i - 2) * 1.2 for r in rates]  # small offsets so the error bars do not overlap
        ax.errorbar(xs, m, yerr=err, marker="o", ms=4, capsize=2, lw=1.4, elinewidth=0.8,
                    label=LABEL[arm], **st)
    ax.set_xlabel("questionnaire answers hidden at test time (%)")
    ax.set_ylabel("test macro-F1 (mean, 95% CI over seeds)")
    ax.set_xticks([100 * r for r in rates])
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ------------------------------------------------------------------------------------- report
def summarise(res: pd.DataFrame, seeds: list[int]) -> pd.DataFrame:
    """Paired differences: fieldwise vs ``none`` of the same arm; natural fusion vs photo-only."""
    out = []
    fw = res[res["analysis"] == "fieldwise"]
    for arm, a in fw.groupby("arm"):
        piv = a.pivot(index="seed", columns="condition", values="macro_f1").loc[seeds]
        for cond in piv.columns:
            if cond == "none":
                continue
            out.append({"analysis": "fieldwise", "arm": arm, "condition": cond,
                        "macro_f1": piv[cond].mean(), "reference": piv["none"].mean(),
                        **paired(piv[cond], piv["none"])})
    nat = res[res["analysis"] == "natural"]
    piv = nat.pivot_table(index=["condition", "seed"], columns="arm", values="macro_f1")
    ns = nat.groupby(["condition", "arm"])["n"].mean()
    for g in NATURAL_GROUPS:
        if g not in piv.index.get_level_values(0):
            continue
        sub = piv.loc[g]
        for arm in FUSION_ARMS:
            if arm in sub:
                out.append({"analysis": "natural", "arm": arm, "condition": g, "macro_f1": sub[arm].mean(),
                            "reference": sub["image_only"].mean(), "n_cases": ns.get((g, arm), np.nan),
                            **paired(sub[arm], sub["image_only"])})
    tab = pd.DataFrame(out)
    tab["p_holm"] = np.nan
    for (an, arm), idx in tab.groupby(["analysis", "arm"]).groups.items():
        kinds = tab.loc[idx, "condition"].str.split(":").str[0]
        for kind in kinds.unique():
            ii = kinds[kinds == kind].index
            tab.loc[ii, "p_holm"] = holm(tab.loc[ii, "p"].to_numpy())
    return tab


def markdown(res: pd.DataFrame, tab: pd.DataFrame, rates: list[float], seeds: list[int]) -> str:
    def f(x):
        return "n/a" if pd.isna(x) else f"{x:+.3f}"

    lines = [f"# E2 (Task 3.5): missing answers by field, natural missingness and curve",
             "", f"Seeds: {seeds}. SCIN test split. Test macro-F1; differences are paired per seed "
             "(mean, t-based 95% CI over seeds, seeds where the difference is negative, Holm-adjusted p).", ""]
    lines += ["## Random removal (curve, `e2_curve.png`)", "",
              "| arm | " + " | ".join(f"r = {r:g}" for r in rates) + " |", "|---" * (len(rates) + 1) + "|"]
    d = res[res["analysis"] == "random"]
    for arm in ["image_only"] + FUSION_ARMS:
        a = d[d["arm"] == arm]
        if a.empty:
            continue
        cells = []
        for r in rates:
            x = a[a["condition"] == f"r={r:g}"]["macro_f1"]
            cells.append(f"{x.mean():.3f} ± {x.std(ddof=1):.3f}")
        lines.append(f"| {LABEL[arm]} | " + " | ".join(cells) + " |")
    fw = tab[tab["analysis"] == "fieldwise"]
    if not fw.empty:
        for kind, title in (("hide", "One field hidden for every case (change vs all answers kept)"),
                            ("only", "Only one field kept (change vs all answers kept)")):
            lines += ["", f"## {title}", "",
                      "| field | " + " | ".join(LABEL[a] for a in FUSION_ARMS) + " |",
                      "|---" * (len(FUSION_ARMS) + 1) + "|"]
            conds = [c for c in fw["condition"].unique() if c.startswith(kind + ":")] + (
                ["all"] if kind == "hide" else [])
            for c in conds:
                cells = []
                for a in FUSION_ARMS:
                    r = fw[(fw["arm"] == a) & (fw["condition"] == c)]
                    if r.empty:
                        cells.append("n/a")
                        continue
                    r = r.iloc[0]
                    star = "*" if r["p_holm"] < 0.05 else ""
                    cells.append(f"{f(r['delta'])} [{f(r['ci_low'])}, {f(r['ci_high'])}] {r['n_neg']}/{r['n']}{star}")
                name = "whole questionnaire" if c == "all" else c.split(":", 1)[1]
                lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines += ["", "\\* Holm-adjusted p < 0.05 (within one arm and one condition type)."]
    nat = tab[tab["analysis"] == "natural"]
    if not nat.empty:
        lines += ["", "## Naturally missing answers in SCIN (fusion minus photo-only, same cases, r = 0)", "",
                  "| group | test cases per seed | photo only | " + " | ".join(LABEL[a] for a in FUSION_ARMS) + " |",
                  "|---" * (len(FUSION_ARMS) + 3) + "|"]
        for g in NATURAL_GROUPS:
            rows = nat[nat["condition"] == g]
            if rows.empty:
                continue
            n = rows["n_cases"].iloc[0]
            flag = " (small)" if n < MIN_GROUP else ""
            cells = []
            for a in FUSION_ARMS:
                r = rows[rows["arm"] == a]
                cells.append("n/a" if r.empty else
                             f"{r.iloc[0]['macro_f1']:.3f} ({f(r.iloc[0]['delta'])} [{f(r.iloc[0]['ci_low'])}, "
                             f"{f(r.iloc[0]['ci_high'])}])")
            lines.append(f"| {g} | {n:.0f}{flag} | {rows['reference'].iloc[0]:.3f} | " + " | ".join(cells) + " |")
        lines += ["", "complete = every field that can be skipped is answered; partial = some skipped; empty = all of them skipped "
                  "(the age question is left out of this count: it always has an answer, "
                  "because 'age unknown' is encoded as an explicit answer, not as missing). "
                  f"Groups under {MIN_GROUP} cases are marked small."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--backbone", default="efficientnet_b0")
    ap.add_argument("--balance", default="weighted_loss")
    ap.add_argument("--no-fieldwise", action="store_true", help="skip the field-wise analysis (needs inference)")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e2")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    preds = pd.concat([load_predictions(a, arm_spec(a, args.backbone, args.balance), args.seeds)
                       for a in ["image_only"] + FUSION_ARMS], ignore_index=True)
    rates = sorted(preds.loc[preds["arm"] != "image_only", "missing_pct"].unique().tolist())
    parts = [curve(preds, rates), natural(preds, args.seeds)]
    if not args.no_fieldwise:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        parts.append(fieldwise(args.seeds, args.backbone, args.balance, device))
    res = pd.concat(parts, ignore_index=True)
    res.to_csv(args.out_dir / "e2_missingness_results.csv", index=False)
    tab = summarise(res, args.seeds)
    tab.to_csv(args.out_dir / "e2_missingness_summary.csv", index=False)
    (args.out_dir / "e2_missingness_table.md").write_text(markdown(res, tab, rates, args.seeds), encoding="utf-8")
    plot_curve(res, rates, args.out_dir / "e2_curve.png")
    log.info("wrote %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
