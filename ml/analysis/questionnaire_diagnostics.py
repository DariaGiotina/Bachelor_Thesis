"""Why does the questionnaire not improve the photo model? Three diagnostics on the saved E1 runs (no retraining).

A. Complementarity: on the test cases, is the questionnaire-only model right more often when the
   photo-only model is wrong than its overall rate (which is what independent errors would give)?
   Also the "oracle" accuracy (either model right): the most any combination of the two could reach.
B. Which questions carry the signal: the questionnaire-only model is re-scored with one question
   hidden (features 0, mask 1 - exactly a missing answer) and with only one question kept.
C. Redundancy: can the photo model "see" the answers? A logistic regression on the pooled features of
   the trained photo-only network (train cases of the seed) predicts each answer on the test cases;
   AUROC 0.5 = not visible in the photo features, 1.0 = fully visible.

Writes ``results/e1/diagnostics/`` (complementarity.csv, field_importance.csv, redundancy.csv,
diagnostics.md; aggregate numbers only).

Usage::

    python analysis/questionnaire_diagnostics.py                 # seeds 0-9
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

ML = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ML), str(ML / "src")]
from data_loading import SCINDataset, load_config  # noqa: E402
from foundation_probe import primary_view  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from models.q_model import QuestionnaireMLP  # noqa: E402
from run_q_only import QuestionnaireDataset  # noqa: E402
from train import field_index  # noqa: E402

log = logging.getLogger("questionnaire_diagnostics")
RUNS = ML / "runs"
IMG = RUNS / "e1_image_only" / "efficientnet_b0_weighted_loss"
QON = RUNS / "e1_questionnaire_only" / "weighted_loss"


# ------------------------------------------------------------------------------- A. complementarity
def complementarity(seeds: list[int]) -> pd.DataFrame:
    rows = []
    for s in seeds:
        a = pd.read_csv(IMG / f"seed{s}" / "predictions.csv", dtype={"case_id": str})
        b = pd.read_csv(QON / f"seed{s}" / "predictions.csv", dtype={"case_id": str})
        a = a[a["split"] == "test"].set_index("case_id")
        b = b[(b["split"] == "test") & (b["missing_pct"] == 0.0)].set_index("case_id").loc[a.index]
        ri, rq = a["true_label"] == a["pred_label"], b["true_label"] == b["pred_label"]
        rows.append({"seed": s, "n": len(a), "acc_photo": ri.mean(), "acc_questionnaire": rq.mean(),
                     "p_q_right_if_photo_wrong": rq[~ri].mean(), "p_q_right_if_photo_right": rq[ri].mean(),
                     "oracle_either_right": (ri | rq).mean(), "same_prediction": (a["pred_label"] == b["pred_label"]).mean()})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- B. field importance
@torch.no_grad()
def field_importance(cfg: dict, seeds: list[int]) -> pd.DataFrame:
    qc, rows = cfg["q_baseline"], []
    for s in seeds:
        ds = QuestionnaireDataset(SCINDataset(cfg, "test", s))
        fields = field_index(ds.q_cols, ds.m_cols)
        names = [m.split("__", 1)[1] for m in ds.m_cols]
        model = QuestionnaireMLP(len(ds.q_cols), len(ds.m_cols), len(ds.classes), qc["hidden"], qc["depth"], qc["dropout"])
        model.load_state_dict(torch.load(QON / "seed_checkpoints" / f"q_only_seed{s}.pt", map_location="cpu"))
        model.eval()
        y = ds.y.numpy()

        def score(hide: list[int]) -> float:
            q, m = ds.q_vec.clone(), ds.q_mask.clone()
            for j in hide:
                q[:, fields[j]] = 0.0
                m[:, j] = 1.0
            p = model(q, m).argmax(1).numpy()
            return f1_score(y, p, labels=np.unique(y), average="macro", zero_division=0)

        full = score([])
        everything = list(range(len(names)))
        for j, n in enumerate(names):
            rows.append({"seed": s, "field": n, "macro_f1_all": full, "drop_when_hidden": full - score([j]),
                         "macro_f1_only_this": score([k for k in everything if k != j]),
                         "answered_share": float((ds.q_mask[:, j] == 0).float().mean())})
        rows.append({"seed": s, "field": "(none: all hidden)", "macro_f1_all": full, "drop_when_hidden": full - score(everything),
                     "macro_f1_only_this": score(everything), "answered_share": np.nan})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------- C. redundancy
@torch.no_grad()
def photo_features(cfg: dict, seed: int, split: str, device) -> tuple[np.ndarray, list[str]]:
    ib = cfg["image_baseline"]
    model = SkinImageBaseline(len(cfg["data"]["classes"]), ib["backbone"], pretrained=False,
                              top_blocks=ib["top_blocks"], drop_rate=ib["drop_rate"]).to(device)
    model.load_state_dict(torch.load(IMG / "seed_checkpoints" / f"img_only_seed{seed}.pt", map_location=device))
    model.eval()
    ds = primary_view(SCINDataset(cfg, split, seed), cfg)  # primary image, no augmentation
    out = []
    for b in DataLoader(ds, batch_size=64, num_workers=0):
        x = b["image"].to(device)
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            f = model.net.forward_head(model.net.forward_features(x), pre_logits=True)
        out.append(f.float().cpu().numpy())
    return np.concatenate(out), list(ds.case_ids)


def answer_targets(feats: pd.DataFrame) -> dict[str, pd.Series]:
    """Binary answers (NaN where the question was not answered)."""
    t = {}
    for field in ("body_area", "texture", "symptoms"):
        answered = feats[f"m__{field}"] == 0
        for c in [c for c in feats.columns if c.startswith(f"f__{field}__")]:
            t[f"{field}: {c.split('__')[2]}"] = feats[c].where(answered)
    rank = feats["f__duration__rank"].where((feats["m__duration"] == 0) & (feats["f__duration__unknown"] == 0))
    t["duration: longer than median"] = (rank > rank.median()).astype(float).where(rank.notna())
    for k in ("age_group", "skin_type"):
        answered = feats[f"m__{k}"] == 0
        if k == "age_group":
            older = feats[[f"f__age_group__age_{a}" for a in ("50_to_59", "60_to_69", "70_to_79")]].sum(axis=1)
            t["age: 50 or older"] = older.where(answered & (feats["f__age_group__age_unknown"] == 0))
        else:
            dark = feats[["f__skin_type__fst5", "f__skin_type__fst6"]].sum(axis=1)
            t["self-reported skin type: V-VI"] = dark.where(answered & (feats["f__skin_type__none_identified"] == 0))
    return t


def redundancy(cfg: dict, seeds: list[int], min_pos: int = 15) -> pd.DataFrame:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    feats = pd.read_parquet(ML / cfg["paths"]["features"])
    feats.index = feats.index.astype(str)
    targets = answer_targets(feats)
    rows = []
    for s in seeds:
        xtr, idtr = photo_features(cfg, s, "train", device)
        xte, idte = photo_features(cfg, s, "test", device)
        sc = StandardScaler().fit(xtr)
        xtr, xte = sc.transform(xtr), sc.transform(xte)
        for name, y in targets.items():
            ytr, yte = y.reindex(idtr).to_numpy(), y.reindex(idte).to_numpy()
            mtr, mte = ~np.isnan(ytr), ~np.isnan(yte)
            if min(ytr[mtr].sum(), (1 - ytr[mtr]).sum()) < min_pos or len(np.unique(yte[mte])) < 2:
                continue
            clf = LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced").fit(xtr[mtr], ytr[mtr])
            rows.append({"seed": s, "answer": name, "auroc": roc_auc_score(yte[mte], clf.predict_proba(xte[mte])[:, 1]),
                         "positive_share": float(np.nanmean(yte[mte])), "n_test": int(mte.sum())})
        log.info("seed %d: redundancy done", s)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--out-dir", type=Path, default=ML / "results" / "e1" / "diagnostics")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config(ML / "configs" / "base.yaml")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    comp = complementarity(args.seeds)
    imp = field_importance(cfg, args.seeds)
    red = redundancy(cfg, args.seeds)
    comp.to_csv(args.out_dir / "complementarity.csv", index=False, float_format="%.4f")
    imp.to_csv(args.out_dir / "field_importance.csv", index=False, float_format="%.4f")
    red.to_csv(args.out_dir / "redundancy.csv", index=False, float_format="%.4f")

    c = comp.drop(columns="seed").agg(["mean", "std"]).T
    fi = imp.groupby("field")[["drop_when_hidden", "macro_f1_only_this", "answered_share"]].agg(["mean", "std"])
    fi = fi.sort_values(("drop_when_hidden", "mean"), ascending=False)
    rd = red.groupby("answer")[["auroc", "positive_share", "n_test"]].mean().sort_values("auroc", ascending=False)
    md = [f"# Why the questionnaire does not improve the photo model (seeds {args.seeds[0]}-{args.seeds[-1]}, test)", "",
          "## A. Complementarity (photo-only vs questionnaire-only predictions)", "",
          "| Quantity | Mean ± sd |", "|---|---|"]
    md += [f"| {k} | {v['mean']:.3f} ± {v['std']:.3f} |" for k, v in c.iterrows()]
    md += ["", "If errors were independent, P(questionnaire right | photo wrong) would equal the questionnaire's overall "
           "accuracy.", "", "## B. Which questions carry the signal (questionnaire-only model)", "",
           "| Question | Macro-F1 drop when hidden | Macro-F1 with only this question | Answered share |",
           "|---|---|---|---|"]
    md += [f"| {f} | {r[('drop_when_hidden', 'mean')]:+.3f} ± {r[('drop_when_hidden', 'std')]:.3f} | "
           f"{r[('macro_f1_only_this', 'mean')]:.3f} | {r[('answered_share', 'mean')]:.2f} |" for f, r in fi.iterrows()]
    md += ["", "## C. Can the photo model see the answers? (AUROC of the answer from the photo features)", "",
           "| Answer | AUROC | Share yes | Test cases |", "|---|---|---|---|"]
    md += [f"| {a} | {r['auroc']:.3f} | {r['positive_share']:.2f} | {r['n_test']:.0f} |" for a, r in rd.iterrows()]
    md += ["", "AUROC 0.5 = the answer is not recoverable from the photo features; 1.0 = fully recoverable."]
    (args.out_dir / "diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
