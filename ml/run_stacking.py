"""Cross-fitted stacking: photo model + questionnaire combined without the photo model's training-set overfit.

Why: in E1 every jointly trained fusion model ignores the questionnaire (hiding all answers costs
nothing, E2), although the questionnaire alone is well above chance. A likely cause is that the
image branch fits the training cases almost perfectly, so on the training data the answers look
useless and the fusion layer learns not to use them, a known problem of multimodal training
(Wang et al., CVPR 2020). Stacking with cross-fitting (Wolpert, 1992) removes that cause:

1. The training split of a seed is cut into K folds (stratified by category). For each fold a
   photo-only model is trained on the other K-1 folds with the E1 recipe (staged fine-tuning,
   weighted loss, early stopping on the validation split) and predicts the held-out fold. Every
   training case thus gets an out-of-fold photo prediction from a model that never saw it, as
   honest as a test prediction. Validation and test cases get the mean probability of the K models.
2. A small combiner, multinomial logistic regression with balanced class weights, is trained on the
   training split. Inputs: the photo log-probabilities (4 values) and the questionnaire
   [q_vec, q_mask]. Its strength C is chosen on validation macro-F1.

Arms (same photo predictions, so their difference isolates the questionnaire):
  stack_photo     combiner on the photo log-probabilities only (the fair reference)
  stack_photo_q   combiner on photo log-probabilities + questionnaire
  stack_q         combiner on the questionnaire only (sanity check against run_q_only.py)
  stack_photo_qmlp  combiner on photo log-probabilities + the log-probabilities of a questionnaire MLP
                  (the run_q_only.py model), also cross-fitted on the same folds; the MLP captures
                  interactions between answers that a linear combiner on raw answers cannot

Test answers are hidden at every rate of ``train.eval_missing_rates`` exactly as in the other
runners (``train.hide_answers``, generator seeded by the split seed, batches of the loader size in
loader order), so ``run_e1.py --arms ... stack_photo stack_photo_q`` compares the arms with paired
tests on the same cases and hidden answers.

Outputs in ``runs/e1_stacking/<backbone>_<balance>/`` (git-ignored):
  seed{k}/folds/photo_fold{f}.pt         fold photo models (state_dict)
  seed{k}/photo_logprobs.npz             out-of-fold train, val and test log-probabilities
  <arm>/seed{k}/predictions.csv          evaluate.py format (+ metrics_summary.*)
  <arm>/seed_runs.csv                    chosen C and macro-F1 per seed

Usage::

    python run_stacking.py --seeds 0 1 2 3 4 5 6 7 8 9
    python run_stacking.py --seeds 0 --folds 2 --epochs 1 --max-batches 3 --num-workers 0   # smoke test
"""
from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, build_transform, get_dataloaders, load_config  # noqa: E402
from engine import image_only_adapt  # noqa: E402
from losses import class_weights  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from models.q_model import QuestionnaireMLP  # noqa: E402
from run_image_only import BACKBONES, BALANCES, build_balanced_training, fit_staged, write_seed_runs  # noqa: E402
from train import field_index, hide_answers  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_stacking")
ARMS = ("stack_photo", "stack_photo_q", "stack_q", "stack_photo_qmlp")
C_GRID = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0]


class Subset(Dataset):
    """Rows ``idx`` of a SCINDataset, keeping the attributes the training code reads."""

    def __init__(self, ds, idx: np.ndarray):
        self.ds, self.idx = ds, np.asarray(idx)
        self.labels, self.classes = ds.labels[self.idx], ds.classes

    def set_epoch(self, epoch: int) -> None:
        self.ds.set_epoch(epoch)

    def __len__(self) -> int:
        return len(self.idx)

    def __getitem__(self, i: int) -> dict:
        return self.ds[int(self.idx[i])]


def eval_copy(ds, cfg: dict):
    """The training cases with the validation/test transform (no augmentation, primary image first)."""
    ev = copy.copy(ds)
    ev.split, ev.transform = "train_eval", build_transform(cfg, train=False)
    return ev


def loader(ds, cfg: dict, shuffle: bool, seed: int) -> DataLoader:
    lc, nw = cfg["loader"], cfg["loader"]["num_workers"]
    return DataLoader(ds, batch_size=lc["batch_size"], shuffle=shuffle, generator=torch.Generator().manual_seed(seed),
                      num_workers=nw, pin_memory=lc["pin_memory"] and torch.cuda.is_available(),
                      persistent_workers=lc["persistent_workers"] and nw > 0)


@torch.no_grad()
def log_probs(model, dl, device) -> np.ndarray:
    model.eval()
    out = []
    for batch in dl:
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            out.append(torch.log_softmax(model(image=batch["image"].to(device)).float(), 1).cpu())
    return torch.cat(out).numpy()


# ----------------------------------------------------------------------------- step 1: photo predictions
def photo_predictions(seed: int, cfg: dict, opts: dict, seed_dir: Path, device) -> dict:
    path = seed_dir / "photo_logprobs.npz"
    if path.exists():
        return dict(np.load(path))
    seed_everything(seed)
    loaders = get_dataloaders(cfg, seed)
    train_ds = loaders["train"].dataset
    k, ib, tc = len(train_ds.classes), cfg["image_baseline"], cfg["train"]
    oof = np.full((len(train_ds), k), np.nan, dtype=np.float32)
    val_lp, test_lp = [], []
    folds = StratifiedKFold(opts["folds"], shuffle=True, random_state=seed).split(np.zeros(len(train_ds)),
                                                                                 train_ds.labels)
    (seed_dir / "folds").mkdir(parents=True, exist_ok=True)
    ev = eval_copy(train_ds, cfg)
    for f, (fit_idx, out_idx) in enumerate(folds):
        log.info("seed %d fold %d/%d: train %d, held out %d", seed, f + 1, opts["folds"], len(fit_idx), len(out_idx))
        fold_loaders = {**loaders, "train": loader(Subset(train_ds, fit_idx), cfg, True, seed * 100 + f)}
        loss_fn, fold_loaders = build_balanced_training(opts["balance"], cfg, seed, fold_loaders, device, False)
        model = SkinImageBaseline(k, ib["backbone"], tc["pretrained"], ib["top_blocks"], ib["drop_rate"]).to(device)
        ckpt = seed_dir / "folds" / f"photo_fold{f}.pt"
        ckpt.unlink(missing_ok=True)
        fold_dir = seed_dir / "folds" / f"fold{f}"
        fold_dir.mkdir(exist_ok=True)
        fit_staged(model, fold_loaders, loss_fn, image_only_adapt, cfg, ckpt, fold_dir, device, seed,
                   opts["epochs"], opts["max_batches"])
        model.load_state_dict(torch.load(ckpt, map_location=device))
        oof[out_idx] = log_probs(model, loader(Subset(ev, out_idx), cfg, False, seed), device)
        val_lp.append(log_probs(model, loaders["val"], device))
        test_lp.append(log_probs(model, loaders["test"], device))
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    def mean_lp(lps):  # mean of the K models' probabilities, back to log space
        return np.log(np.mean(np.exp(np.stack(lps)), axis=0) + 1e-12).astype(np.float32)

    out = {"train": oof, "val": mean_lp(val_lp), "test": mean_lp(test_lp)}
    if np.isnan(out["train"]).any():
        raise RuntimeError("some training cases got no out-of-fold prediction")
    np.savez(path, **out)
    return out


def train_q_mlp(x_tr, y_tr, x_va, y_va, cfg: dict, seed: int) -> QuestionnaireMLP:
    """The run_q_only.py model (same sizes, optimiser, weighted loss and early stopping), on arrays."""
    qc, k = cfg["q_baseline"], len(cfg["data"]["classes"])
    torch.manual_seed(seed)
    n_f = x_tr[1].shape[1]
    model = QuestionnaireMLP(x_tr[0].shape[1], n_f, k, qc["hidden"], qc["depth"], qc["dropout"])
    opt = torch.optim.AdamW(model.parameters(), lr=qc["lr"], weight_decay=qc["weight_decay"])
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_weights(y_tr, k))
    q, m, y = (torch.from_numpy(np.ascontiguousarray(a)) for a in (*x_tr, y_tr))
    gen, bs = torch.Generator().manual_seed(seed), cfg["loader"]["batch_size"]
    best, best_state, bad = -1.0, None, 0
    for _ in range(qc["epochs"]):
        model.train()
        for idx in torch.randperm(len(y), generator=gen).split(bs):
            opt.zero_grad()
            loss_fn(model(q_vec=q[idx], q_mask=m[idx]), y[idx]).backward()
            opt.step()
        pred = q_log_probs(model, *x_va).argmax(1)
        f1 = f1_score(y_va, pred, labels=np.unique(y_va), average="macro")
        if f1 > best:
            best, best_state, bad = f1, copy.deepcopy(model.state_dict()), 0
        else:
            bad += 1
            if bad >= qc["early_stopping_patience"]:
                break
    model.load_state_dict(best_state)
    return model


@torch.no_grad()
def q_log_probs(model, q: np.ndarray, m: np.ndarray) -> np.ndarray:
    model.eval()
    return torch.log_softmax(model(q_vec=torch.from_numpy(np.ascontiguousarray(q)),
                                   q_mask=torch.from_numpy(np.ascontiguousarray(m))), 1).numpy()


def q_predictions(seed: int, cfg: dict, opts: dict, dss: dict, fields, seed_dir: Path) -> dict:
    """Out-of-fold questionnaire-MLP log-probabilities on the photo folds; test at every missing rate."""
    path = seed_dir / "q_logprobs.npz"
    if path.exists():
        return dict(np.load(path))
    tr, va, te = dss["train"], dss["val"], dss["test"]
    rates, bs = cfg["train"]["eval_missing_rates"], cfg["loader"]["batch_size"]
    hidden = {r: hidden_q(te, fields, r, seed, bs) for r in rates}
    oof = np.full((len(tr), len(tr.classes)), np.nan, dtype=np.float32)
    val_lp, test_lp = [], {r: [] for r in rates}
    folds = StratifiedKFold(opts["folds"], shuffle=True, random_state=seed).split(np.zeros(len(tr)), tr.labels)
    for f, (fit_idx, out_idx) in enumerate(folds):
        model = train_q_mlp((tr.q_vec[fit_idx], tr.q_mask[fit_idx]), tr.labels[fit_idx], (va.q_vec, va.q_mask),
                            va.labels, cfg, seed * 100 + f)
        oof[out_idx] = q_log_probs(model, tr.q_vec[out_idx], tr.q_mask[out_idx])
        val_lp.append(q_log_probs(model, va.q_vec, va.q_mask))
        for r in rates:
            test_lp[r].append(q_log_probs(model, *hidden[r]))
    mean = lambda lps: np.log(np.mean(np.exp(np.stack(lps)), axis=0) + 1e-12).astype(np.float32)  # noqa: E731
    out = {"train": oof, "val": mean(val_lp), **{f"test_{r}": mean(v) for r, v in test_lp.items()}}
    np.savez(path, **out)
    return out


# ----------------------------------------------------------------------------- step 2: combiners
def hidden_q(ds, fields, rate: float, seed: int, batch_size: int):
    """q_vec, q_mask with a share ``rate`` of fields hidden, drawn exactly as the other runners do."""
    q, m = torch.from_numpy(ds.q_vec.copy()), torch.from_numpy(ds.q_mask.copy())
    if rate == 0:
        return q.numpy(), m.numpy()
    gen, qs, ms = torch.Generator().manual_seed(seed), [], []
    for i in range(0, len(q), batch_size):
        a, b = hide_answers(q[i:i + batch_size], m[i:i + batch_size], fields, 0.0, rate, gen)
        qs.append(a)
        ms.append(b)
    return torch.cat(qs).numpy(), torch.cat(ms).numpy()


def features(arm: str, lp: np.ndarray, q: np.ndarray, m: np.ndarray, qlp: np.ndarray | None = None) -> np.ndarray:
    parts = {"stack_photo": [lp], "stack_photo_q": [lp, q, m], "stack_q": [q, m], "stack_photo_qmlp": [lp, qlp]}[arm]
    return np.concatenate(parts, axis=1)


def fit_combiner(x_tr, y_tr, x_va, y_va, seed: int):
    """Balanced multinomial logistic regression; C chosen on validation macro-F1 (ties: smaller C)."""
    scaler = StandardScaler().fit(x_tr)
    best = None
    for c in C_GRID:
        clf = LogisticRegression(C=c, class_weight="balanced", max_iter=5000, random_state=seed)
        clf.fit(scaler.transform(x_tr), y_tr)
        f1 = f1_score(y_va, clf.predict(scaler.transform(x_va)), labels=np.unique(y_va), average="macro")
        if best is None or f1 > best[0] + 1e-9:
            best = (f1, c, clf)
    return scaler, best


def frame(ds, proba: np.ndarray, split: str, seed: int, rate: float) -> pd.DataFrame:
    s = lambda v: pd.Series(v).where(lambda x: x > 0).astype("Int64")  # noqa: E731
    return pd.DataFrame({"case_id": [str(int(c)) for c in ds.case_ids], "split": split,
                         "true_label": [ds.classes[i] for i in ds.labels],
                         "pred_label": [ds.classes[i] for i in proba.argmax(1)],
                         "confidence": proba.max(1).round(6), "eFST": s(ds.efst), "eMST": s(ds.emst),
                         "seed": seed, "missing_pct": rate})


def run(options: dict | None = None) -> None:
    defaults = {"config": ROOT / "configs" / "base.yaml", "backbone": "efficientnet_b0", "balance": "weighted_loss",
                "seeds": list(range(10)), "folds": 5, "epochs": None, "max_batches": None, "num_workers": None,
                "n_boot": None, "out_root": ROOT / "runs" / "e1_stacking", "skip_existing": True}
    opts = {**defaults, **(options or {})}
    if opts["balance"] != "weighted_loss":  # the sampler arm draws from the whole training split, not a fold
        raise ValueError("run_stacking.py supports --balance weighted_loss only")
    cfg = copy.deepcopy(load_config(opts["config"]))
    cfg["image_baseline"]["backbone"] = opts["backbone"] or cfg["image_baseline"]["backbone"]
    if opts["num_workers"] is not None:
        cfg["loader"]["num_workers"] = opts["num_workers"]
    root = Path(opts["out_root"]) / f"{cfg['image_baseline']['backbone']}_{opts['balance']}"
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    n_boot = str(opts["n_boot"] or cfg["train"].get("n_boot", 1000))
    rates, bs = cfg["train"]["eval_missing_rates"], cfg["loader"]["batch_size"]
    for seed in opts["seeds"]:
        if opts["skip_existing"] and all((root / a / f"seed{seed}" / "metrics_summary.csv").exists() for a in ARMS):
            log.info("seed %d already done, skipped", seed)
            continue
        lp = photo_predictions(seed, cfg, opts, root / f"seed{seed}", device)
        dss = {s: get_dataloaders(cfg, seed, s).dataset for s in ("train", "val", "test")}
        fields = field_index(dss["train"].q_cols, dss["train"].m_cols)
        y = {s: d.labels for s, d in dss.items()}
        qlp = q_predictions(seed, cfg, opts, dss, fields, root / f"seed{seed}")
        for arm in ARMS:
            x_tr = features(arm, lp["train"], dss["train"].q_vec, dss["train"].q_mask, qlp["train"])
            x_va = features(arm, lp["val"], dss["val"].q_vec, dss["val"].q_mask, qlp["val"])
            scaler, (val_f1, c, clf) = fit_combiner(x_tr, y["train"], x_va, y["val"], seed)
            out_dir = root / arm / f"seed{seed}"
            out_dir.mkdir(parents=True, exist_ok=True)
            frames = [frame(dss["val"], clf.predict_proba(scaler.transform(x_va)), "val", seed, 0.0)]
            rec = {"arm": arm, "seed": seed, "C": c, "val_macro_f1": val_f1}
            for r in rates:
                q, m = hidden_q(dss["test"], fields, r, seed, bs)
                proba = clf.predict_proba(scaler.transform(features(arm, lp["test"], q, m, qlp[f"test_{r}"])))
                frames.append(frame(dss["test"], proba, "test", seed, r))
                rec[f"test_macro_f1_missing_{r}"] = f1_score(y["test"], proba.argmax(1), labels=np.unique(y["test"]),
                                                             average="macro")
            pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
            harness.main([str(out_dir / "predictions.csv"), "--split", "test", "--n-boot", n_boot])
            write_seed_runs(root / arm / "seed_runs.csv", [rec])
            log.info("seed %d %s: C=%g val %.3f test r=0 %.3f r=1 %.3f", seed, arm, c, val_f1,
                     rec["test_macro_f1_missing_0.0"], rec["test_macro_f1_missing_1.0"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--backbone", choices=BACKBONES, default="efficientnet_b0")
    ap.add_argument("--balance", choices=BALANCES, default="weighted_loss")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--max-batches", type=int, default=None)
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=None)
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "e1_stacking")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(vars(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
