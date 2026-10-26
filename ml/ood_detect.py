"""Task 4.2b: out-of-scope detector for the app model (frozen DINOv2 ViT-B/14 + linear probe).

E4 showed that low confidence is not a safety filter: the calibrated DINOv2 probe answered
confidently for most images of conditions it was never trained on, including biopsy-proven
malignant lesions. This script tests whether a distance in the encoder's feature space catches
those images, i.e. flags a photo as unlike every SCIN training case before the classifier answers.

Scores (higher = more unlike the training data), fitted per seed on the train cases of that seed:
  msp          1 - calibrated largest class probability of the probe (baseline; Hendrycks & Gimpel 2017)
  mahalanobis  smallest Mahalanobis distance to a class mean, one shared covariance with Ledoit-Wolf
               shrinkage (Lee et al. 2018; Ledoit & Wolf 2004)
  knn          1 - cosine similarity to the k-th nearest training case on L2-normalised features
               (Sun et al. 2022), k = 10
The primary detector (knn, k = 10) was fixed before any out-of-scope result was seen; the others and
the k sensitivity are reported for comparison only, nothing is selected on the test sets.
Threshold: the 95th percentile of the score on the seed's validation cases, so 5% of in-scope
validation cases are flagged (the price paid on normal use).

Test sets (all images scored by every seed's detector; intervals resample whole images):
  scin_test        the seed's SCIN test cases (in scope): false alarms, by eFST and eMST
  scin_ood         SCIN cases whose dermatologist differentials all lie outside the four categories
                   (``labels/scin_near_ood.csv``): same phones, same contributors, other conditions
  fitz_in/out      Fitzpatrick17k images inside / outside the categories (atlas photos: other domain)
  ddi_out          DDI images outside the categories; ddi_malignant: biopsy-proven malignant lesions
Combined rule for the app: "see a professional" when the detector flags the photo OR the calibrated
confidence is below the E4 tau (80% coverage). Reported: the share answered with a confident label.

Outputs in ``results/e4/``: e4_ood.md, e4_ood_auroc.csv (per seed), e4_ood_groups.csv, e4_ood.png.

Usage::

    python ood_detect.py --make-list      # once: writes labels/scin_near_ood.csv
    python scripts/download_scin_images.py --case-ids labels/scin_near_ood.csv
    python scripts/resize_image_cache.py
    python ood_detect.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.covariance import LedoitWolf
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from abstain import group_report  # noqa: E402
from calibrate import apply_temperature  # noqa: E402
from data_loading import ROOT, build_transform, load_config  # noqa: E402
from run_e4 import SCALES, external_features  # noqa: E402
from skinconcern.metrics import efst_group, emst_group  # noqa: E402

log = logging.getLogger("ood_detect")
ARM = "probe_dinov2"
PROBE_DIR = ROOT / "runs" / "foundation_probe" / "timm_vit_base_patch14_dinov2.lvd142m"
NEAR_OOD = ROOT / "labels" / "scin_near_ood.csv"
METHODS = ["msp", "mahalanobis", "knn"]
PRIMARY = "knn"
K, K_GRID = 10, (1, 5, 10, 20, 50)
SETS = {"scin_test": "SCIN test (in scope)", "scin_ood": "SCIN, other conditions",
        "fitz_in": "Fitzpatrick17k in scope", "fitz_out": "Fitzpatrick17k out of scope",
        "ddi_out": "DDI out of scope", "ddi_malignant": "DDI malignant"}
OOD_SETS = [s for s in SETS if s != "scin_test"]


# ------------------------------------------------------------------------------- out-of-scope list
def make_near_ood(path: Path = NEAR_OOD) -> pd.DataFrame:
    """SCIN cases with a dermatologist label whose differentials all map outside the four categories."""
    sys.path.insert(0, str(ROOT / "labels"))
    import build_labels as bl

    cfg = bl.load_map(ROOT / "labels" / "label_map.yaml")
    cases, raw = bl.audit.load(ROOT / "data" / "scin")
    df = bl.audit.derive(bl.audit.merge(cases, raw))
    parsed = df[bl.audit.WEIGHTED_LABEL_COL].map(bl.audit._parse_dict)
    keep = (parsed.map(len) > 0) & (parsed.map(lambda d: bl.in_scope_weight(d, cfg)) == 0)
    out = pd.DataFrame({"top_condition": df.loc[keep, "_top_condition"],
                        "eFST": df.loc[keep, "_efst"].astype("Int64"),
                        "eMST": df.loc[keep, "_emst_us"].astype("Int64")}).reset_index()
    out.to_csv(path, index=False)
    log.info("%d out-of-scope SCIN cases -> %s", len(out), path)
    return out


class SCINCaseImages(Dataset):
    """Primary image of the given SCIN cases, preprocessed like the val/test split (cache copy first)."""

    def __init__(self, cfg: dict, case_ids: list[str]):
        paths = {k: ROOT / v for k, v in cfg["paths"].items()}
        cases = pd.read_csv(paths["cases_csv"], dtype=str).set_index("case_id")
        col = cfg["data"]["primary_image_column"]
        self.case_ids = list(case_ids)
        self.names = [Path(cases.loc[c, col]).name for c in self.case_ids]
        self.dirs = [paths["image_cache_dir"], paths["images_dir"]]
        self.transform = build_transform(cfg, train=False)
        self.size = cfg["data"]["image_size"]

    def __len__(self) -> int:
        return len(self.case_ids)

    def __getitem__(self, i: int) -> dict:
        for d in self.dirs:
            p = d / (Path(self.names[i]).stem + ".png" if d == self.dirs[0] else self.names[i])
            if p.exists():
                with Image.open(p) as im:
                    img, ok = np.asarray(im.convert("RGB")), 1
                break
        else:
            img, ok = np.zeros((self.size, self.size, 3), dtype=np.uint8), 0
        return {"image": self.transform(image=img)["image"], "image_ok": torch.tensor(ok), "case_id": self.case_ids[i]}


@torch.no_grad()
def near_ood_features(batch_size: int = 32) -> dict:
    """DINOv2 features of the out-of-scope SCIN cases, same preprocessing as ``foundation_probe.py``. Cached."""
    import copy

    import foundation_probe as fp
    from run_e1 import PROBES

    cache = ROOT / "runs" / "external_eval" / "e4" / f"features_{ARM}_scin_ood.pt"
    if cache.exists():
        return torch.load(cache, weights_only=True)
    meta = pd.read_csv(NEAR_OOD, dtype={"case_id": str})
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    enc = fp.load_encoder(*PROBES[ARM], device)
    cfg = copy.deepcopy(load_config(ROOT / "configs" / "base.yaml"))
    cfg["data"]["image_size"] = enc.image_size
    cfg["normalize"] = {"mean": list(enc.mean), "std": list(enc.std)}
    feats, ok, ids = [], [], []
    for b in DataLoader(SCINCaseImages(cfg, meta["case_id"].tolist()), batch_size=batch_size, num_workers=4):
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            feats.append(enc.forward(b["image"].to(device)).float().cpu())
        ok.append(b["image_ok"])
        ids += list(b["case_id"])
    ok = torch.cat(ok).bool()
    if (~ok).any():
        log.warning("%d out-of-scope SCIN cases have no image on disk; they are left out", int((~ok).sum()))
    out = {"features": torch.cat(feats)[ok], "case_id": [i for i, k in zip(ids, ok.tolist()) if k]}
    torch.save(out, cache)
    return out


# ----------------------------------------------------------------------------------------- scores
def fit_mahalanobis(x: np.ndarray, y: np.ndarray):
    """Class means and the precision of one shared (tied) covariance with Ledoit-Wolf shrinkage."""
    means = np.stack([x[y == c].mean(0) for c in np.unique(y)])
    prec = LedoitWolf().fit(x - means[np.searchsorted(np.unique(y), y)]).precision_
    return means, prec


def mahalanobis_score(x: np.ndarray, model) -> np.ndarray:
    means, prec = model
    return np.min([np.einsum("ij,jk,ik->i", x - m, prec, x - m) for m in means], axis=0)


def l2n(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=1, keepdims=True).clip(1e-12)


def knn_score(x: np.ndarray, train: np.ndarray, k: int = K) -> np.ndarray:
    """1 - cosine similarity to the k-th nearest training case (``train`` already L2-normalised)."""
    sim = l2n(x) @ train.T
    return 1 - np.partition(sim, -k, axis=1)[:, -k]


def threshold(val_scores: np.ndarray, keep: float = 0.95) -> float:
    """Score above which a case is flagged: ``keep`` of the in-scope validation cases stay below it."""
    return float(np.quantile(np.asarray(val_scores, float), keep))


def probe_probs(x: np.ndarray, probe: dict) -> np.ndarray:
    w, b = probe["state_dict"]["weight"].numpy(), probe["state_dict"]["bias"].numpy()
    z = (x - probe["mean"].numpy()) / probe["std"].numpy() @ w.T + b
    z = np.exp(z - z.max(1, keepdims=True))
    return z / z.sum(1, keepdims=True)


# ------------------------------------------------------------------------------------- test data
def load_sets(classes: list[str]) -> dict[str, pd.DataFrame | np.ndarray]:
    """Features and metadata of every out-of-scope / external set (the same images for every seed)."""
    sets = {}
    nf = near_ood_features()
    meta = pd.read_csv(NEAR_OOD, dtype={"case_id": str}).set_index("case_id").loc[nf["case_id"]].reset_index()
    sets["scin_ood"] = (nf["features"].numpy(), meta.assign(true_label="out_of_scope")[
        ["case_id", "true_label", "eFST", "eMST"]])
    ddi_meta = pd.read_csv(ROOT / "data" / "ddi" / "ddi_metadata.csv")
    malignant = set(ddi_meta.loc[ddi_meta["malignant"], "DDI_file"].astype(str).str.rsplit(".", n=1).str[0])
    for dataset in ("fitzpatrick17k", "ddi"):
        ef = external_features(ARM, dataset)
        if ef["classes"] != classes:
            raise ValueError(f"{dataset} features were built for classes {ef['classes']}")
        lab = ef["label"].numpy()
        m = pd.DataFrame({"case_id": [str(c) for c in ef["case_id"]],
                          "true_label": [classes[i] if i >= 0 else "out_of_scope" for i in lab],
                          "eFST": pd.Series(ef["eFST"].numpy()).where(lambda s: s > 0).astype("Int64"),
                          "eMST": pd.NA})
        f = ef["features"].numpy()
        if dataset == "fitzpatrick17k":
            sets["fitz_in"], sets["fitz_out"] = (f[lab >= 0], m[lab >= 0]), (f[lab < 0], m[lab < 0])
        else:
            mal = m["case_id"].str.zfill(6).isin(malignant).to_numpy()
            sets["ddi_out"] = (f[lab < 0], m[lab < 0])
            sets["ddi_malignant"] = (f[mal], m[mal])
    return {k: (f, m.reset_index(drop=True)) for k, (f, m) in sets.items()}


# --------------------------------------------------------------------------------------- per seed
def score_seed(seed: int, feats: dict, sets: dict, splits: dict, cal: pd.Series) -> tuple[pd.DataFrame, list]:
    """Fit the detectors on the seed's train cases, threshold on its val cases, score every set."""
    pos = {c: i for i, c in enumerate(feats["case_id"])}
    idx = {s: np.array([pos[c] for c in splits[str(seed)][s] if c in pos]) for s in ("train", "val", "test")}
    x_all, y_all = feats["features"].numpy(), feats["label"].numpy()
    classes = feats["classes"]
    probe = torch.load(PROBE_DIR / f"probe_seed{seed}.pt", map_location="cpu", weights_only=True)
    x_tr, y_tr = x_all[idx["train"]], y_all[idx["train"]]
    maha, train_n = fit_mahalanobis(x_tr, y_tr), l2n(x_tr)

    test_meta = pd.DataFrame({"case_id": [feats["case_id"][i] for i in idx["test"]],
                              "true_label": [classes[i] for i in y_all[idx["test"]]],
                              "eFST": pd.Series(feats["eFST"][idx["test"]].numpy()).where(lambda s: s > 0).astype("Int64"),
                              "eMST": pd.Series(feats["eMST"][idx["test"]].numpy()).where(lambda s: s > 0).astype("Int64")})
    all_sets = {"val": (x_all[idx["val"]], None), "scin_test": (x_all[idx["test"]], test_meta), **sets}

    def scores(x):
        p = apply_temperature(probe_probs(x, probe), cal["T"])
        return p, {"msp": 1 - p.max(1), "mahalanobis": mahalanobis_score(x, maha), "knn": knn_score(x, train_n)}

    _, val_s = scores(all_sets["val"][0])
    thr = {m: threshold(v) for m, v in val_s.items()}
    frames, ksens = [], []
    test_s = None
    for name, (x, meta) in all_sets.items():
        if name == "val":
            continue
        p, s = scores(x)
        d = meta.assign(seed=seed, set=name, pred=np.array(classes)[p.argmax(1)], conf_cal=p.max(1))
        d["correct"] = d["pred"].to_numpy() == d["true_label"].to_numpy()
        d["confident"] = d["conf_cal"] >= cal["tau"]
        for m in METHODS:
            d[f"score_{m}"], d[f"flag_{m}"] = s[m], s[m] > thr[m]
        frames.append(d)
        if name == "scin_test":
            test_s = {k: knn_score(x, train_n, k) for k in K_GRID}
        else:
            for k in K_GRID:
                o = knn_score(x, train_n, k)
                ksens.append({"seed": seed, "set": name, "k": k,
                              "auroc": roc_auc_score(np.r_[np.zeros(len(test_s[k])), np.ones(len(o))],
                                                     np.r_[test_s[k], o])})
    return pd.concat(frames, ignore_index=True), ksens


def check_probe(seed: int, scored: pd.DataFrame) -> None:
    """The probe recomputed from features must give the predictions stored by foundation_probe.py."""
    stored = pd.read_csv(PROBE_DIR / f"seed{seed}" / "predictions.csv", dtype={"case_id": str})
    stored = stored[stored["split"] == "test"].set_index("case_id")["pred_label"]
    mine = scored[scored["set"] == "scin_test"].set_index("case_id")["pred"]
    agree = (stored.loc[mine.index] == mine).mean()
    if agree < 0.999:
        raise ValueError(f"seed {seed}: recomputed probe agrees with stored predictions on only {agree:.1%}")


# --------------------------------------------------------------------------------------- reports
def auroc_table(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed, d in scored.groupby("seed"):
        neg = d[d["set"] == "scin_test"]
        for name in OOD_SETS:
            pos = d[d["set"] == name]
            for m in METHODS:
                y = np.r_[np.zeros(len(neg)), np.ones(len(pos))]
                rows.append({"seed": seed, "set": name, "method": m,
                             "auroc": roc_auc_score(y, np.r_[neg[f"score_{m}"], pos[f"score_{m}"]]),
                             "flag_rate": pos[f"flag_{m}"].mean(), "false_alarm": neg[f"flag_{m}"].mean()})
    return pd.DataFrame(rows)


def rule_groups(scored: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    """Per set and tone group: share flagged by the primary detector, share answered confidently
    with confidence only (E4) and with the combined rule. SCIN test resamples cases within seeds,
    the other sets resample whole images."""
    reports = []
    for name in SETS:
        d = scored[scored["set"] == name].copy()
        d["eFST_group"], d["eMST_group"] = d["eFST"].map(efst_group), d["eMST"].map(emst_group)
        rules = {"flag": ~d[f"flag_{PRIMARY}"], "confidence": d["confident"],
                 "combined": d["confident"] & ~d[f"flag_{PRIMARY}"]}
        scales = ["eFST", "eMST"] if name.startswith("scin") else ["eFST"]
        for rule, answered in rules.items():
            for scale in scales:
                _, groups, contrasts = SCALES[scale]
                r = group_report(d.assign(answered=answered.to_numpy()), f"{scale}_group", groups, contrasts,
                                 n_boot, cluster=None if name == "scin_test" else "case_id")
                reports.append(r.assign(set=name, rule=rule))
    return pd.concat(reports, ignore_index=True)


def plot(groups: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ["scin_test", "scin_ood", "fitz_out", "ddi_out", "ddi_malignant"]
    tones = ["I-II", "III-IV", "V-VI"]
    fig, axes = plt.subplots(1, len(names), figsize=(13, 3.4), sharey=True)
    for ax, name in zip(axes, names):
        for i, (rule, color, label) in enumerate((("confidence", "#9b9b9b", "confidence only (E4)"),
                                                  ("combined", "#2471a3", "confidence + detector"))):
            v = groups[(groups.set == name) & (groups.rule == rule) & (groups.scale == "eFST_group")
                       & (groups.metric == "coverage")].set_index("group").loc[tones]
            x = np.arange(len(tones)) + (i - 0.5) * 0.38
            ax.bar(x, 100 * v["value"], 0.38, color=color, label=label,
                   yerr=[100 * (v["value"] - v["ci_low"]), 100 * (v["ci_high"] - v["value"])], capsize=2,
                   error_kw={"elinewidth": 0.7})
        ax.set_xticks(np.arange(len(tones)))
        ax.set_xticklabels([f"eFST {t}" for t in tones], fontsize=7)
        ax.set_title(SETS[name], fontsize=8)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("answered with a label (%)")
    axes[0].legend(fontsize=7, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def markdown(au: pd.DataFrame, groups: pd.DataFrame, ks: pd.DataFrame, n_img: dict, seeds) -> str:
    def ms(x, k=1, nd=3):
        return f"{k * x.mean():.{nd}f} ± {k * x.std(ddof=1):.{nd}f}"

    def cell(name, rule, scale, group, metric="coverage"):
        r = groups[(groups.set == name) & (groups.rule == rule) & (groups.scale == scale)
                   & (groups.group == group) & (groups.metric == metric)]
        if r.empty or pd.isna(r.iloc[0]["value"]):
            return "n/a"
        r = r.iloc[0]
        sign = "+" if " - " in group and r["value"] >= 0 else ""
        return f"{sign}{100 * r['value']:.1f} [{100 * r['ci_low']:.1f}, {100 * r['ci_high']:.1f}]"

    out = ["# Task 4.2b: out-of-scope detector for the DINOv2 app model", "",
           f"Seeds {seeds}. Detectors fitted on each seed's SCIN train features (frozen DINOv2 ViT-B/14), "
           "threshold = 95th percentile on the seed's validation cases. Primary detector: kNN, k = 10 (fixed in "
           "advance). Mean ± sd over seeds; brackets: 95% bootstrap interval (SCIN test: cases within seeds; "
           "other sets: whole images).", "",
           "Images per set: " + ", ".join(f"{SETS[k]} {v}" for k, v in n_img.items()) + ".", "",
           "## Separation from the SCIN test cases (AUROC; 0.5 = chance, 1 = perfect)", "",
           "| Set | " + " | ".join(METHODS) + " |", "|---" * (len(METHODS) + 1) + "|"]
    for name in OOD_SETS:
        out.append(f"| {SETS[name]} | " + " | ".join(ms(au[(au.set == name) & (au.method == m)]["auroc"])
                                                      for m in METHODS) + " |")
    out += ["", "## Share flagged at the validation threshold (%)", "",
            "| Set | " + " | ".join(METHODS) + " |", "|---" * (len(METHODS) + 1) + "|",
            "| SCIN test (in scope), false alarms | " + " | ".join(
                ms(au[(au.set == "scin_ood") & (au.method == m)]["false_alarm"], 100, 1) for m in METHODS) + " |"]
    for name in OOD_SETS:
        out.append(f"| {SETS[name]} | " + " | ".join(ms(au[(au.set == name) & (au.method == m)]["flag_rate"], 100, 1)
                                                      for m in METHODS) + " |")
    out += ["", "## kNN sensitivity to k (AUROC, mean over seeds; k = 10 was fixed before the run)", "",
            "| Set | " + " | ".join(f"k = {k}" for k in K_GRID) + " |", "|---" * (len(K_GRID) + 1) + "|"]
    for name in OOD_SETS:
        out.append(f"| {SETS[name]} | " + " | ".join(f"{ks[(ks.set == name) & (ks.k == k)]['auroc'].mean():.3f}"
                                                      for k in K_GRID) + " |")
    for scale, groups_ in (("eFST", ["ALL", "I-II", "III-IV", "V-VI", "V-VI - I-II"]),
                           ("eMST", ["ALL", "1-3", "4-6", "7-10", "4-6 - 1-3"])):
        names = list(SETS) if scale == "eFST" else ["scin_test", "scin_ood"]
        out += ["", f"## Answered with a label (%), by {scale} group", "",
                "Flagged by kNN: share NOT flagged. Confidence only: the E4 rule (calibrated confidence >= tau). "
                "Combined: confident and not flagged. On in-scope sets a higher share is better; on out-of-scope "
                "and malignant sets a lower share is safer.", "",
                "| Set | Rule | " + " | ".join(groups_) + " |", "|---" * (len(groups_) + 2) + "|"]
        for name in names:
            for rule, label in (("flag", "not flagged by kNN"), ("confidence", "confidence only"),
                                ("combined", "combined")):
                out.append(f"| {SETS[name]} | {label} | " + " | ".join(cell(name, rule, f"{scale}_group", g)
                                                                      for g in groups_) + " |")
    out += ["", "## Selective accuracy on SCIN test (%), answered cases only", "",
            "| Rule | ALL | eFST I-II | eFST III-IV | eFST V-VI |", "|---|---|---|---|---|"]
    for rule in ("confidence", "combined"):
        out.append(f"| {rule} | " + " | ".join(cell("scin_test", rule, "eFST_group", g, "selective_accuracy")
                                              for g in ("ALL", "I-II", "III-IV", "V-VI")) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--make-list", action="store_true", help="write labels/scin_near_ood.csv and stop")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "results" / "e4")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.make_list:
        make_near_ood()
        return 0

    feats = torch.load(PROBE_DIR / "features.pt", weights_only=True)
    splits = json.loads((ROOT / "splits" / "train_val_test_splits.json").read_text(encoding="utf-8"))
    cal = pd.read_csv(args.out_dir / "e4_calibration.csv")
    cal = cal[(cal["arm"] == ARM) & cal["group"].isna()].astype({"seed": int}).set_index("seed")
    sets = load_sets(feats["classes"])
    scored, ks = [], []
    for s in args.seeds:
        d, k = score_seed(s, feats, sets, splits, cal.loc[s])
        check_probe(s, d)
        scored.append(d)
        ks += k
        t = d[d["set"] == "scin_test"]
        log.info("seed %d: false alarms %.3f, flagged on SCIN other conditions %.3f, DDI malignant %.3f", s,
                 t[f"flag_{PRIMARY}"].mean(), d.loc[d["set"] == "scin_ood", f"flag_{PRIMARY}"].mean(),
                 d.loc[d["set"] == "ddi_malignant", f"flag_{PRIMARY}"].mean())
    scored, ks = pd.concat(scored, ignore_index=True), pd.DataFrame(ks)
    au = auroc_table(scored)
    groups = rule_groups(scored, args.n_boot)
    n_img = {name: int(scored[(scored["set"] == name) & (scored["seed"] == args.seeds[0])].shape[0]) for name in SETS}
    au.to_csv(args.out_dir / "e4_ood_auroc.csv", index=False)
    groups.to_csv(args.out_dir / "e4_ood_groups.csv", index=False)
    (args.out_dir / "e4_ood.md").write_text(markdown(au, groups, ks, n_img, args.seeds), encoding="utf-8")
    plot(groups, args.out_dir / "e4_ood.png")
    log.info("wrote %s", args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
