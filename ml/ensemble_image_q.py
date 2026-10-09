"""Diagnostic E1 arm: late ensemble of the separately trained photo-only and questionnaire-only models.

Per split seed, the two saved checkpoints (``run_image_only.py`` and ``run_q_only.py``) are combined
by log-linear pooling of their class probabilities:

    p(c) ∝ p_image(c)^w * p_questionnaire(c)^(1 - w)

with the weight w chosen on the validation split (macro-F1, grid 0, 0.1, ..., 1; never on test).
No network is retrained. The question it answers: if the ensemble beats the photo alone, the
questionnaire carries information the photo lacks and the jointly trained fusion models fail to use
it; if it does not, the photo already holds what the questionnaire says.

The test split is scored at every rate of ``train.eval_missing_rates`` (answers hidden in the
questionnaire model's input exactly as in ``run_q_only.py`` and ``run_fusion.py``), and the
predictions are written in the evaluate.py format, so ``run_e1.py --arms ... ensemble_image_q``
compares it with the other arms.

Usage::

    python ensemble_image_q.py                       # efficientnet_b0, weighted_loss, seeds 0-4
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
import yaml
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, SCINDataset, get_dataloaders, load_config  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from models.q_model import QuestionnaireMLP  # noqa: E402
from run_image_only import BACKBONES, BALANCES, aggregate_seeds  # noqa: E402
from run_q_only import QuestionnaireDataset, make_q_adapt  # noqa: E402
from train import field_index, predictions_frame  # noqa: E402

log = logging.getLogger("ensemble_image_q")
WEIGHTS = np.round(np.linspace(0, 1, 11), 2)


@torch.no_grad()
def log_probs(model, loader, adapt, device) -> tuple[np.ndarray, dict]:
    """Log-probabilities and the per-case fields of predictions_frame, in loader order."""
    model.eval()
    out, y, ef, em, ids = [], [], [], [], []
    for batch in loader:
        inputs = {k: v.to(device) for k, v in adapt(batch, False).items()}
        out.append(torch.log_softmax(model(**inputs).float(), 1).cpu())
        y.append(batch["label"].numpy())
        ef.append(np.asarray(batch["eFST"]))
        em.append(np.asarray(batch["eMST"]))
        ids.append(np.asarray(batch["case_id"]))
    return torch.cat(out).numpy(), {"y_true": np.concatenate(y), "eFST": np.concatenate(ef),
                                    "eMST": np.concatenate(em), "case_id": np.concatenate(ids)}


def pool(lp_img: np.ndarray, lp_q: np.ndarray, w: float) -> np.ndarray:
    z = w * lp_img + (1 - w) * lp_q
    z = z - z.max(1, keepdims=True)
    p = np.exp(z)
    return p / p.sum(1, keepdims=True)


def macro_f1(y, p) -> float:
    return float(f1_score(y, p.argmax(1), labels=np.unique(y), average="macro", zero_division=0))


def run_seed(seed: int, cfg: dict, img_ckpt: Path, q_ckpt: Path, out_dir: Path, device) -> dict:
    ib, qc = cfg["image_baseline"], cfg["q_baseline"]
    img_loaders = get_dataloaders(cfg, seed)
    classes = img_loaders["val"].dataset.classes
    q_loaders = {s: DataLoader(QuestionnaireDataset(SCINDataset(cfg, s, seed)), batch_size=cfg["loader"]["batch_size"])
                 for s in ("val", "test")}
    for s in ("val", "test"):  # same cases in the same order, so probabilities can be combined row by row
        assert list(img_loaders[s].dataset.case_ids) == [str(int(c)) for c in q_loaders[s].dataset.case_ids]
    qds = q_loaders["val"].dataset
    fields = field_index(qds.q_cols, qds.m_cols)
    img = SkinImageBaseline(len(classes), ib["backbone"], pretrained=False, top_blocks=ib["top_blocks"],
                            drop_rate=ib["drop_rate"]).to(device)
    img.load_state_dict(torch.load(img_ckpt, map_location=device))
    qm = QuestionnaireMLP(len(qds.q_cols), len(qds.m_cols), len(classes), qc["hidden"], qc["depth"],
                          qc["dropout"]).to(device)
    qm.load_state_dict(torch.load(q_ckpt, map_location=device))
    image_adapt = lambda b, t: {"image": b["image"]}  # noqa: E731

    lp_img = {s: log_probs(img, img_loaders[s], image_adapt, device) for s in ("val", "test")}
    lp_q_val, _ = log_probs(qm, q_loaders["val"], make_q_adapt(fields, 0.0, 0.0, seed), device)
    y_val = lp_img["val"][1]["y_true"]
    scores = {float(w): macro_f1(y_val, pool(lp_img["val"][0], lp_q_val, w)) for w in WEIGHTS}
    w = max(scores, key=lambda k: (scores[k], k))  # ties -> more weight on the photo
    log.info("seed %d: w_image = %.1f chosen on validation (val macro-F1 %.3f; photo alone %.3f, questionnaire "
             "alone %.3f)", seed, w, scores[w], scores[1.0], scores[0.0])

    frames = []
    for split, rates in (("val", [0.0]), ("test", cfg["train"]["eval_missing_rates"])):
        meta = lp_img[split][1]
        for r in rates:
            lp_q, _ = log_probs(qm, q_loaders[split], make_q_adapt(fields, 0.0, r, seed), device)
            p = pool(lp_img[split][0], lp_q, w)
            res = {**meta, "y_pred": p.argmax(1), "confidence": p.max(1)}
            frames.append(predictions_frame(res, classes, split, seed, r))
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    return {"seed": seed, "w_image": w, "val_macro_f1": scores[w], "val_photo_only": scores[1.0],
            "val_questionnaire_only": scores[0.0], "val_grid": json.dumps(scores)}


def run(options: dict | None = None) -> pd.DataFrame:
    opts = {"config": ROOT / "configs" / "base.yaml", "backbone": "efficientnet_b0", "balance": "weighted_loss",
            "seeds": [0, 1, 2, 3, 4], "n_boot": 1000, "skip_existing": False, **(options or {})}
    cfg = load_config(opts["config"])
    cfg["image_baseline"]["backbone"] = opts["backbone"]
    img_root = ROOT / "runs" / "e1_image_only" / f"{opts['backbone']}_{opts['balance']}" / "seed_checkpoints"
    q_root = ROOT / "runs" / "e1_questionnaire_only" / opts["balance"] / "seed_checkpoints"
    root = ROOT / "runs" / "e1_ensemble" / f"{opts['backbone']}_{opts['balance']}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    runs, flats = [], []
    for seed in opts["seeds"]:
        out_dir = root / f"seed{seed}"
        out_dir.mkdir(exist_ok=True)
        if not (opts["skip_existing"] and (out_dir / "metrics_summary.csv").exists()):
            runs.append(run_seed(seed, cfg, img_root / f"img_only_seed{seed}.pt", q_root / f"q_only_seed{seed}.pt",
                                 out_dir, device))
            pd.DataFrame(runs).to_csv(root / "seed_runs.csv", index=False)
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", str(opts["n_boot"])])
        flats.append(pd.read_csv(out_dir / "metrics_summary.csv", dtype={"seed": str}))
    summary = aggregate_seeds(pd.concat(flats, ignore_index=True))
    summary.insert(0, "experiment", "E1_ensemble_image_q")
    summary.to_csv(root / "e1_ensemble_test.csv", index=False)
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backbone", choices=BACKBONES, default="efficientnet_b0")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(vars(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
