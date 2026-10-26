"""E4 / Task 4.2 (RQ4): calibration and abstention by skin tone, for the candidate app models.

Arms (same SCIN splits and test cases, seeds 0-9):
  image_only           fine-tuned EfficientNet-B0 (E1)
  fusion_film          photo + questionnaire, FiLM fusion (best fusion arm in E1)
  probe_dinov2         frozen DINOv2 ViT-B/14 + linear probe (E5)
  probe_panderm_large  frozen PanDerm-Large + linear probe (E5)
  probe_dermlip        frozen DermLIP ViT-B/16 + linear probe (E5)

Per seed: temperature T fitted on validation (``calibrate.py``); ECE and NLL on test before and
after; tau chosen on calibrated validation confidence for a target coverage (``abstain.py``),
applied to test. Reported: calibration per arm (and ECE per tone group after calibration), the
risk-coverage curve and AURC (area under it; T does not change it because it keeps the ranking of
confidences), and the abstention metrics per eFST / eMST group with paired group differences.
External check: the photo-only and DINOv2 models on Fitzpatrick17k and DDI (zero-shot, every image,
including diagnoses outside our categories, where abstaining is the right answer), with the SCIN T and tau.

Outputs in ``results/e4/``: e4_calibration.csv, e4_abstention.csv, e4_table.md,
e4_risk_coverage.png, e4_abstention_by_tone.png, e4_reliability.png.

Usage::

    python calibrate.py --export image_only fusion_film   # once: full probabilities for these arms
    python run_e4.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from abstain import choose_tau, group_report  # noqa: E402
from calibrate import apply_temperature, fit_temperature, nll, to_logits  # noqa: E402
from data_loading import ROOT  # noqa: E402
from run_e1 import arm_spec  # noqa: E402
from skinconcern.metrics import aurc, efst_group, emst_group, expected_calibration_error, macro_f1  # noqa: E402

log = logging.getLogger("run_e4")
ARMS = ["image_only", "fusion_film", "probe_dinov2", "probe_panderm_large", "probe_dermlip"]
LABEL = {"image_only": "EfficientNet-B0 fine-tuned", "fusion_film": "FiLM fusion (photo + questionnaire)",
         "probe_dinov2": "DINOv2 + probe", "probe_panderm_large": "PanDerm-Large + probe",
         "probe_dermlip": "DermLIP + probe"}
COLORS = {"image_only": "black", "fusion_film": "#8e44ad", "probe_dinov2": "#2471a3",
          "probe_panderm_large": "#c0392b", "probe_dermlip": "#229954"}
SCALES = {"eFST": (efst_group, ["I-II", "III-IV", "V-VI"], [("V-VI", "I-II"), ("III-IV", "I-II")]),
          "eMST": (emst_group, ["1-3", "4-6", "7-10"], [("4-6", "1-3"), ("7-10", "1-3")])}
N_BINS = 15


# ------------------------------------------------------------------------------------ loading
def load_arm(arm: str, seeds: list[int], backbone: str = "efficientnet_b0", balance: str = "weighted_loss"):
    """Val + test rows per seed with prob_<class> columns, labels and tones."""
    d = arm_spec(arm, backbone, balance)["dir"]
    frames = []
    for s in seeds:
        pred = pd.read_csv(d / f"seed{s}" / "predictions.csv", dtype={"case_id": str})
        pred = pred[pred["missing_pct"] == 0.0]
        if not any(c.startswith("prob_") for c in pred.columns):
            probs = pd.read_csv(d / f"seed{s}" / "probs.csv", dtype={"case_id": str})
            pred = pred.merge(probs, on=["case_id", "split"], validate="one_to_one")
        frames.append(pred.assign(seed=s))
    return pd.concat(frames, ignore_index=True)


def classes_of(df: pd.DataFrame) -> list[str]:
    return [c.removeprefix("prob_") for c in df.columns if c.startswith("prob_")]


# ------------------------------------------------------------------------------- per seed work
def calibrate_seed(df: pd.DataFrame, classes: list[str], coverage: float) -> tuple[pd.DataFrame, dict]:
    pc = [f"prob_{c}" for c in classes]
    y = {sp: df[df.split == sp]["true_label"].map({c: i for i, c in enumerate(classes)}).to_numpy() for sp in ("val", "test")}
    p = {sp: df[df.split == sp][pc].to_numpy(float) for sp in ("val", "test")}
    t = fit_temperature(to_logits(p["val"]), y["val"])
    pc_test = apply_temperature(p["test"], t)
    conf_val = apply_temperature(p["val"], t).max(1)
    tau = choose_tau(conf_val, coverage)
    test = df[df.split == "test"].copy()
    test["pred_idx"] = pc_test.argmax(1)
    test["correct"] = test["pred_idx"].to_numpy() == y["test"]
    test["conf_raw"] = p["test"].max(1)
    test["conf_cal"] = pc_test.max(1)
    test["answered"] = test["conf_cal"] >= tau
    corr = test["correct"].to_numpy()
    info = {"T": t, "tau": tau,
            "nll_before": nll(to_logits(p["test"]), y["test"]), "nll_after": nll(to_logits(p["test"]), y["test"], t),
            "ece_before": expected_calibration_error(test["conf_raw"], corr, N_BINS),
            "ece_after": expected_calibration_error(test["conf_cal"], corr, N_BINS),
            "aurc": aurc(test["conf_cal"], corr), "accuracy": corr.mean(),
            "macro_f1": macro_f1(y["test"], test["pred_idx"].to_numpy()),
            "coverage": test["answered"].mean(),
            "selective_accuracy": corr[test["answered"].to_numpy()].mean(),
            "selective_macro_f1": macro_f1(y["test"][test["answered"].to_numpy()],
                                           test["pred_idx"].to_numpy()[test["answered"].to_numpy()])}
    return test, info


def ci_t(x) -> tuple[float, float]:
    x = np.asarray(x, float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return x.mean() - h, x.mean() + h


# ------------------------------------------------------------------------------------ external
EXT_ARMS = ["image_only", "probe_dinov2"]
EXT_SETS = ["fitzpatrick17k", "ddi"]


@torch.no_grad()
def external_predictions(arm: str, dataset: str, seeds: list[int]) -> pd.DataFrame:
    """Class probabilities of every seed's model on every image of an external set, including the
    images whose diagnosis is outside our categories (true_label ``out_of_scope``). Cached."""
    import yaml
    from torch.utils.data import DataLoader

    import external_datasets as ext
    from models.image_model import SkinImageBaseline

    cache = ROOT / "runs" / "external_eval" / "e4" / f"{arm}_{dataset}.csv"
    if cache.exists():
        df = pd.read_csv(cache, dtype={"case_id": str})
        if set(seeds) <= set(df["seed"].unique()):
            return df[df["seed"].isin(seeds)]
    spec = arm_spec(arm, "efficientnet_b0", "weighted_loss")
    cfg = yaml.safe_load((ROOT / "runs" / "e1_image_only" / "efficientnet_b0_weighted_loss" / "config_used.yaml")
                         .read_text(encoding="utf-8"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    frames = []
    if arm == "image_only":  # every batch is loaded once and scored by all seed models
        ds = ext.DATASET_CLASSES[dataset](cfg, keep_all=True)
        ib = cfg["image_baseline"]
        models = {}
        for s in seeds:
            m = SkinImageBaseline(len(ds.classes), ib["backbone"], False, ib["top_blocks"], ib["drop_rate"])
            m.load_state_dict(torch.load(spec["dir"] / "seed_checkpoints" / f"img_only_seed{s}.pt",
                                         map_location="cpu", weights_only=True))
            models[s] = m.to(device).eval()
        probs, labels, efst, ids = {s: [] for s in seeds}, [], [], []
        for b in DataLoader(ds, batch_size=64, shuffle=False, num_workers=4, persistent_workers=False):
            x = b["image"].to(device, non_blocking=True)
            for s, m in models.items():
                with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                    probs[s].append(m(x).float().softmax(1).cpu())
            labels.append(b["label"].numpy())
            efst.append(b["eFST"].numpy())
            ids += list(b["case_id"])
        labels, efst = np.concatenate(labels), np.concatenate(efst)
        for s in seeds:
            p = torch.cat(probs[s]).numpy()
            df = pd.DataFrame({"case_id": ids, "true_label": [ds.classes[i] if i >= 0 else "out_of_scope" for i in labels],
                               "eFST": pd.Series(efst).where(lambda x: x > 0).astype("Int64"), "seed": s})
            for j, c in enumerate(ds.classes):
                df[f"prob_{c}"] = p[:, j]
            frames.append(df)
    elif arm in ("probe_dinov2", "probe_panderm_large", "probe_dermlip"):
        ef = external_features(arm, dataset)
        f, labels, efst, ids = ef["features"], ef["label"].numpy(), ef["eFST"].numpy(), ef["case_id"]
        for s in seeds:
            pr = torch.load(spec["dir"] / f"probe_seed{s}.pt", map_location="cpu", weights_only=True)
            lin = torch.nn.Linear(f.shape[1], len(pr["classes"]))
            lin.load_state_dict(pr["state_dict"])
            p = lin((f - pr["mean"]) / pr["std"]).softmax(1).numpy()
            df = pd.DataFrame({"case_id": ids, "true_label": [pr["classes"][i] if i >= 0 else "out_of_scope"
                                                               for i in labels],
                               "eFST": pd.Series(efst).where(lambda x: x > 0).astype("Int64"), "seed": s})
            for j, c in enumerate(pr["classes"]):
                df[f"prob_{c}"] = p[:, j]
            frames.append(df)
    else:
        raise ValueError(f"no external predictions for arm {arm!r}")
    out = pd.concat(frames, ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False)
    return out


@torch.no_grad()
def external_features(arm: str, dataset: str) -> dict:
    """Frozen-encoder features of every image of an external set (``keep_all``: out-of-scope images
    get label -1), with the same preprocessing as the SCIN features of the probe. Cached."""
    import copy

    import yaml
    from torch.utils.data import DataLoader

    import external_datasets as ext
    import foundation_probe as fp
    from run_e1 import PROBES

    cache = ROOT / "runs" / "external_eval" / "e4" / f"features_{arm}_{dataset}.pt"
    if cache.exists():
        return torch.load(cache, weights_only=True)
    cfg = yaml.safe_load((ROOT / "runs" / "e1_image_only" / "efficientnet_b0_weighted_loss" / "config_used.yaml")
                         .read_text(encoding="utf-8"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    backbone, weights = PROBES[arm]
    enc = fp.load_encoder(backbone, weights, device)
    ecfg = copy.deepcopy(cfg)
    ecfg["data"]["image_size"] = enc.image_size
    ecfg["normalize"] = {"mean": list(enc.mean), "std": list(enc.std)}
    ds = ext.DATASET_CLASSES[dataset](ecfg, keep_all=True)
    feats, labels, efst, ids = [], [], [], []
    for b in DataLoader(ds, batch_size=64, shuffle=False, num_workers=4):
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            feats.append(enc.forward(b["image"].to(device)).float().cpu())
        labels.append(b["label"])
        efst.append(b["eFST"])
        ids += list(b["case_id"])
    out = {"features": torch.cat(feats), "label": torch.cat(labels), "eFST": torch.cat(efst), "case_id": ids,
           "classes": ds.classes}
    cache.parent.mkdir(parents=True, exist_ok=True)
    torch.save(out, cache)
    return out


def ddi_malignant(cal: pd.DataFrame, seeds: list[int], n_boot: int) -> pd.DataFrame:
    """DDI lesions confirmed malignant by biopsy (all outside our categories): share answered without
    the "see a professional" advice, i.e. given a confident benign-category label, by skin tone."""
    meta = pd.read_csv(ROOT / "data" / "ddi" / "ddi_metadata.csv")
    meta = meta.assign(case_id=meta["DDI_file"].astype(str).str.rsplit(".", n=1).str[0])[["case_id", "malignant"]]
    _, groups, contrasts = SCALES["eFST"]
    reports = []
    for arm in EXT_ARMS:
        e = external_predictions(arm, "ddi", seeds)
        e = e.assign(case_id=e["case_id"].astype(str).str.zfill(6)).merge(meta, on="case_id", validate="many_to_one")
        classes = [c.removeprefix("prob_") for c in e.columns if c.startswith("prob_")]
        parts = []
        for s in seeds:
            d = e[(e["seed"] == s) & e["malignant"]].copy()
            row = cal[(cal["arm"] == arm) & (cal["seed"] == s)].iloc[0]
            p = apply_temperature(d[[f"prob_{c}" for c in classes]].to_numpy(float), row["T"])
            d["answered"], d["correct"] = p.max(1) >= row["tau"], False
            parts.append(d)
        d = pd.concat(parts, ignore_index=True)
        d["eFST_group"] = d["eFST"].map(efst_group)
        reports.append(group_report(d, "eFST_group", groups, contrasts, n_boot, cluster="case_id")
                       .assign(arm=arm, dataset="ddi", scope="malignant"))
    return pd.concat(reports, ignore_index=True)


def external(cal: pd.DataFrame, seeds: list[int], n_boot: int) -> pd.DataFrame:
    """Abstention on external sets with each arm's SCIN T and tau: in-scope images (accuracy, abstention)
    and out-of-scope images (the model should abstain). Image-level cluster bootstrap."""
    _, groups, contrasts = SCALES["eFST"]
    reports = []
    for arm in EXT_ARMS:
        for dataset in EXT_SETS:
            e = external_predictions(arm, dataset, seeds)
            classes = [c.removeprefix("prob_") for c in e.columns if c.startswith("prob_")]
            parts = []
            for s in seeds:
                d = e[e["seed"] == s].copy()
                row = cal[(cal["arm"] == arm) & (cal["seed"] == s)].iloc[0]
                p = apply_temperature(d[[f"prob_{c}" for c in classes]].to_numpy(float), row["T"])
                d["correct"] = np.array(classes)[p.argmax(1)] == d["true_label"].to_numpy()
                d["answered"] = p.max(1) >= row["tau"]
                parts.append(d)
            d = pd.concat(parts, ignore_index=True)
            d["eFST_group"] = d["eFST"].map(efst_group)
            for scope, sub in (("in_scope", d[d["true_label"] != "out_of_scope"]),
                               ("out_of_scope", d[d["true_label"] == "out_of_scope"])):
                if len(sub):
                    reports.append(group_report(sub, "eFST_group", groups, contrasts, n_boot, cluster="case_id")
                                   .assign(arm=arm, dataset=dataset, scope=scope))
            log.info("%s on %s: %d images (%d out of scope)", arm, dataset, d["case_id"].nunique(),
                     d.loc[d["true_label"] == "out_of_scope", "case_id"].nunique())
    return pd.concat(reports, ignore_index=True)


# --------------------------------------------------------------------------------------- figures
def plot_risk_coverage(tests: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grid = np.linspace(0.2, 1.0, 33)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for arm, t in tests.items():
        curves = []
        for _, d in t.groupby("seed"):
            conf, corr = d["conf_cal"].to_numpy(), d["correct"].to_numpy(float)
            order = np.argsort(-conf, kind="stable")
            cum = np.cumsum(corr[order]) / np.arange(1, len(conf) + 1)
            curves.append([1 - cum[max(1, int(np.ceil(c * len(conf)))) - 1] for c in grid])
        ax.plot(100 * grid, np.mean(curves, 0), label=LABEL[arm], color=COLORS[arm], lw=1.6,
                ls="--" if arm == "image_only" else "-")
    ax.set_xlabel("coverage: cases answered (%)")
    ax.set_ylabel("risk: error rate on answered cases")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_abstention_by_tone(ab: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8), sharey=True)
    for ax, (scale, (_, groups, _)) in zip(axes, SCALES.items()):
        width = 0.8 / len(ARMS)
        for i, arm in enumerate(ARMS):
            d = ab[(ab.arm == arm) & (ab.scale == f"{scale}_group") & (ab.metric == "abstention_rate")
                   & ab.group.isin(groups)].set_index("group").loc[groups]
            x = np.arange(len(groups)) + (i - (len(ARMS) - 1) / 2) * width
            ax.bar(x, 100 * d["value"], width, color=COLORS[arm], label=LABEL[arm],
                   yerr=[100 * (d["value"] - d["ci_low"]), 100 * (d["ci_high"] - d["value"])], capsize=2,
                   error_kw={"elinewidth": 0.7})
        ax.set_xticks(np.arange(len(groups)))
        ax.set_xticklabels([f"{scale} {g}" for g in groups])
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("abstention rate on test (%)")
    axes[0].legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_reliability(tests: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    edges = np.linspace(0, 1, 11)
    for ax, col, title in ((axes[0], "conf_raw", "before temperature scaling"),
                           (axes[1], "conf_cal", "after temperature scaling")):
        ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls=":")
        for arm, t in tests.items():
            conf, corr = t[col].to_numpy(), t["correct"].to_numpy(float)
            idx = np.clip(np.digitize(conf, edges[1:-1]), 0, len(edges) - 2)
            xs = [conf[idx == b].mean() for b in range(len(edges) - 1) if (idx == b).sum() >= 20]
            ys = [corr[idx == b].mean() for b in range(len(edges) - 1) if (idx == b).sum() >= 20]
            ax.plot(xs, ys, marker="o", ms=3, color=COLORS[arm], label=LABEL[arm],
                    ls="--" if arm == "image_only" else "-")
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("confidence")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("accuracy")
    axes[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------------------------------- report
def markdown(cal: pd.DataFrame, ab: pd.DataFrame, ext: pd.DataFrame | None, seeds, coverage) -> str:
    def m(arm, col, nd=3):
        x = cal[cal.arm == arm][col]
        return f"{x.mean():.{nd}f} ± {x.std(ddof=1):.{nd}f}"

    def cell(d, arm, scale, group, metric, pct=True):
        r = d[(d.arm == arm) & (d.scale == scale) & (d.group == group) & (d.metric == metric)]
        if r.empty or pd.isna(r.iloc[0]["value"]):
            return "n/a"
        r, k = r.iloc[0], 100 if pct else 1
        sign = "+" if " - " in group and r["value"] >= 0 else ""
        return f"{sign}{k * r['value']:.1f} [{k * r['ci_low']:.1f}, {k * r['ci_high']:.1f}]"

    out = [f"# E4 (Task 4.2, RQ4): calibration and abstention by skin tone",
           "", f"Seeds {seeds}, SCIN test split. Temperature T fitted on validation per seed. Abstention: "
           f"answer only if calibrated confidence >= tau, tau set on validation for {100 * coverage:.0f}% coverage. "
           "Mean ± sd over seeds; brackets: 95% interval.", "",
           "## Calibration and selective prediction", "",
           "| Model | T | ECE before | ECE after | NLL before | NLL after | AURC | accuracy | test coverage | selective accuracy |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        out.append(f"| {LABEL[arm]} | {m(arm, 'T', 2)} | {m(arm, 'ece_before')} | {m(arm, 'ece_after')} | "
                   f"{m(arm, 'nll_before')} | {m(arm, 'nll_after')} | {m(arm, 'aurc')} | {m(arm, 'accuracy')} | "
                   f"{m(arm, 'coverage')} | {m(arm, 'selective_accuracy')} |")
    base = cal[cal.arm == "image_only"].set_index("seed")
    out += ["", "AURC difference vs EfficientNet-B0 fine-tuned (paired over seeds; negative = better ranking "
            "of right and wrong answers by confidence):", ""]
    for arm in ARMS[1:]:
        d = cal[cal.arm == arm].set_index("seed")["aurc"] - base["aurc"]
        lo, hi = ci_t(d)
        p = stats.ttest_1samp(d, 0).pvalue
        out.append(f"- {LABEL[arm]}: {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}], better in {(d < 0).sum()}/{len(d)} seeds, t p = {p:.3f}")
    for scale, (_, groups, contrasts) in SCALES.items():
        sc = f"{scale}_group"
        cols = groups + [f"{a} - {b}" for a, b in contrasts]
        n = ab[(ab.scale == sc) & (ab.metric == "coverage") & (ab.arm == "image_only")].set_index("group")["n_cases"]
        for metric, title in (("abstention_rate", "Abstention rate (%)"),
                              ("selective_accuracy", "Selective accuracy (%) on answered cases"),
                              ("abstention_precision", "Abstention precision (%): declined cases that would have been wrong")):
            out += ["", f"## {title}, by {scale} group", "",
                    "| Model | " + " | ".join(f"{g} (n={n.get(g, 0):.0f})" if " - " not in g else g for g in cols) + " |",
                    "|---" * (len(cols) + 1) + "|"]
            for arm in ARMS:
                out.append(f"| {LABEL[arm]} | " + " | ".join(cell(ab, arm, sc, g, metric) for g in cols) + " |")
    out += ["", "n = test cases pooled over the seeds (SCIN: different test split per seed; intervals from a case "
            "bootstrap within each seed). Differences are paired (same bootstrap resamples)."]
    if ext is not None and len(ext):
        _, groups, contrasts = SCALES["eFST"]
        cols = ["ALL"] + groups + [f"{a} - {b}" for a, b in contrasts]
        out += ["", "## External sets (zero-shot; each model's SCIN T and tau)", "",
                "Every seed's model scores the same external images, so the intervals resample whole images "
                "(cluster bootstrap). In scope: diagnoses that map to our four categories. Out of scope: every other "
                "diagnosis (the model was never trained on them, so abstaining is the right answer). Malignant (DDI "
                "only): biopsy-confirmed malignant lesions; coverage = share answered with a confident benign label, "
                "without the advice to see a professional (lower is safer).", "",
                "| Set | Model | Images | Metric | " + " | ".join(cols) + " |", "|---" * (len(cols) + 4) + "|"]
        for dataset in EXT_SETS:
            for scope, metrics in (("in_scope", ("accuracy", "abstention_rate", "selective_accuracy")),
                                   ("out_of_scope", ("abstention_rate",)), ("malignant", ("coverage",))):
                for arm in EXT_ARMS:
                    d = ext[(ext.dataset == dataset) & (ext.scope == scope)]
                    if d[d.arm == arm].empty:
                        continue
                    n_img = d[(d.arm == arm) & (d.metric == "coverage") & (d.group == "ALL")]["n_cases"].iloc[0]
                    for metric in metrics:
                        out.append(f"| {dataset} | {LABEL[arm]} | {scope.replace('_', ' ')}, "
                                   f"{n_img / len(seeds):.0f} | {metric} | "
                                   + " | ".join(cell(d, arm, "eFST_group", c, metric) for c in cols) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--coverage", type=float, default=0.8, help="target coverage for tau (validation)")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--no-external", action="store_true", help="skip Fitzpatrick17k / DDI (needs their images)")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e4")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cal_rows, tests, ab = [], {}, []
    for arm in ARMS:
        df = load_arm(arm, args.seeds)
        classes = classes_of(df)
        parts = []
        for s in args.seeds:
            t, info = calibrate_seed(df[df.seed == s], classes, args.coverage)
            cal_rows.append({"arm": arm, "seed": s, **info})
            parts.append(t)
        t = pd.concat(parts, ignore_index=True)
        t["eFST_group"], t["eMST_group"] = t["eFST"].map(efst_group), t["eMST"].map(emst_group)
        for scale, (_, groups, contrasts) in SCALES.items():
            ab.append(group_report(t, f"{scale}_group", groups, contrasts, args.n_boot).assign(arm=arm))
            for g in groups:  # ECE per tone after calibration, pooled over seeds
                d = t[t[f"{scale}_group"] == g]
                cal_rows.append({"arm": arm, "seed": "pooled", "group": f"{scale} {g}", "n": len(d),
                                 "ece_before": expected_calibration_error(d["conf_raw"], d["correct"], N_BINS),
                                 "ece_after": expected_calibration_error(d["conf_cal"], d["correct"], N_BINS)})
        tests[arm] = t
        c = pd.DataFrame([r for r in cal_rows if r["arm"] == arm and r["seed"] != "pooled"])
        log.info("%s: T %.2f, ECE %.3f -> %.3f, coverage %.3f, selective acc %.3f", arm, c["T"].mean(),
                 c["ece_before"].mean(), c["ece_after"].mean(), c["coverage"].mean(), c["selective_accuracy"].mean())
    cal_all = pd.DataFrame(cal_rows)
    cal = cal_all[cal_all["seed"] != "pooled"].astype({"seed": int})
    ab = pd.concat(ab, ignore_index=True).assign(dataset="scin")
    ext = None if args.no_external else pd.concat([external(cal, args.seeds, args.n_boot),
                                                   ddi_malignant(cal, args.seeds, args.n_boot)], ignore_index=True)
    cal_all.to_csv(args.out_dir / "e4_calibration.csv", index=False)
    pd.concat([ab] + ([ext] if ext is not None else []), ignore_index=True).to_csv(
        args.out_dir / "e4_abstention.csv", index=False)
    (args.out_dir / "e4_table.md").write_text(markdown(cal, ab, ext, args.seeds, args.coverage), encoding="utf-8")
    plot_risk_coverage(tests, args.out_dir / "e4_risk_coverage.png")
    plot_abstention_by_tone(ab, args.out_dir / "e4_abstention_by_tone.png")
    plot_reliability(tests, args.out_dir / "e4_reliability.png")
    log.info("wrote %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
