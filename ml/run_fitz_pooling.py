"""E7: does adding Fitzpatrick17k training images make the SCIN photo model more accurate?

Research-only experiment. The shipped app model stays SCIN-only (Fitzpatrick17k images were
received from the authors under an agreement to delete them after the research, so no model that
ships may depend on them). Two ways of using the extra images are compared with the E1 photo-only
model (``run_image_only.py``, same backbone, same staged recipe, same split seeds):

  fitz_pooled    data pooling: the training set is SCIN train + the Fitzpatrick17k train fold of the
                 seed, trained together in one staged run; class weights come from the pooled labels.
  fitz_pretrain  sequential transfer: a staged run on the Fitzpatrick17k train fold only (ImageNet
                 start), then the best of it is fine-tuned with the same staged recipe on SCIN train.

Model selection (early stopping) always uses the SCIN validation split, because the app's target is
SCIN-like phone photos. Fitzpatrick17k folds come from ``splits/make_fitzpatrick_splits.py``:
near-duplicates and same-patient photos are kept on one side, about 20% of the groups form the
test fold of each seed. Every model is tested on two sets:

  test        SCIN test split of the seed (paired with E1 photo-only on the same cases)
  fitz_test   Fitzpatrick17k test fold of the seed (never trained on); the E1 photo-only reference
              here is its zero-shot result (``external_datasets.py``, filtered to the fold)

Outputs (git-ignored) in ``runs/e7_fitzpatrick/<backbone>_<arm>/``: seed_checkpoints/, seed<k>/
(log.csv, predictions.csv with val / test / fitz_test rows, evaluate.py metrics), seed_runs.csv.
The tables go to ``results/e7/`` (e7_summary.csv, e7_table.md).

Usage::

    python run_fitz_pooling.py --arms fitz_pooled fitz_pretrain --seeds 0 1 2 3 4 5 6 7 8 9
    python run_fitz_pooling.py --no-train --seeds 0 1 2 3 4 5 6 7 8 9          # tables only
    python run_fitz_pooling.py --epochs 1 --max-batches 3 --seeds 0 --n-boot 50 --out-root runs/smoke_e7
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
import torch.nn as nn
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
import run_e1  # noqa: E402
from data_loading import ROOT, build_transform, get_dataloaders, load_config  # noqa: E402
from engine import evaluate, image_only_adapt  # noqa: E402
from external_datasets import Fitzpatrick17kDataset, predict_frame  # noqa: E402
from losses import class_weights  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402
from run_image_only import fit_staged, write_seed_runs  # noqa: E402
from train import predictions_frame  # noqa: E402
from utils.seed import seed_everything  # noqa: E402

log = logging.getLogger("run_fitz_pooling")
ARMS = ("fitz_pooled", "fitz_pretrain")
REFERENCE = "image_only"
SPLITS_CSV = ROOT / "splits" / "fitzpatrick17k_splits.csv"
ZERO_SHOT_CSV = ROOT / "runs" / "external_eval" / "fitz_full_{run}" / "external_eval.csv"


# ------------------------------------------------------------------------------------------ data
class FitzpatrickTrainView(Dataset):
    """Fitzpatrick17k training images shaped like SCIN train items.

    No questionnaire: ``q_vec`` is zero and every ``q_mask`` bit is 1 (all answers missing), so the
    item can share a batch with SCIN items; the image-only model reads the image only. ``case_id`` is
    negative (-1, -2, ...) so it never collides with a SCIN id. Augmentation as SCIN train, with a
    per-item draw from (seed, epoch, index).
    """

    def __init__(self, cfg: dict, rows: pd.DataFrame, seed: int, n_q: int, n_m: int):
        self.cfg, self.seed = cfg, seed
        self.rows = rows.reset_index(drop=True)
        self.classes = list(cfg["data"]["classes"])
        self.labels = self.rows["label"].map({c: i for i, c in enumerate(self.classes)}).to_numpy(np.int64)
        self.efst = pd.to_numeric(self.rows["eFST"], errors="coerce").fillna(-1).to_numpy(np.int64)
        self.n_q, self.n_m = n_q, n_m
        self.transform = build_transform(cfg, train=True)
        self._epoch = torch.zeros(1, dtype=torch.int64).share_memory_()

    def set_epoch(self, epoch: int) -> None:
        self._epoch[0] = epoch

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict:
        rng = np.random.default_rng([self.seed, int(self._epoch[0]), idx, 17])
        try:
            with Image.open(self.rows.at[idx, "image_path"]) as im:
                img, ok = np.asarray(im.convert("RGB")), 1
        except (OSError, ValueError):
            size = self.cfg["data"]["image_size"]
            img, ok = np.zeros((size, size, 3), dtype=np.uint8), 0
        self.transform.set_random_seed(int(rng.integers(2**31 - 1)))
        return {"image": self.transform(image=img)["image"], "q_vec": torch.zeros(self.n_q),
                "q_mask": torch.ones(self.n_m), "label": torch.tensor(self.labels[idx]),
                "eFST": torch.tensor(self.efst[idx]), "eMST": torch.tensor(-1),
                "case_id": torch.tensor(-(idx + 1), dtype=torch.int64), "image_ok": torch.tensor(ok)}


class PooledDataset(Dataset):
    """Several training datasets read as one (index runs through them in order)."""

    def __init__(self, parts: list[Dataset]):
        self.parts = parts
        self.classes = parts[0].classes
        self.offsets = np.cumsum([0] + [len(p) for p in parts])
        self.labels = np.concatenate([p.labels for p in parts])

    def set_epoch(self, epoch: int) -> None:
        for p in self.parts:
            p.set_epoch(epoch)

    def __len__(self) -> int:
        return int(self.offsets[-1])

    def __getitem__(self, idx: int) -> dict:
        k = int(np.searchsorted(self.offsets, idx, side="right") - 1)
        return self.parts[k][idx - int(self.offsets[k])]


def fitz_folds(seed: int, splits_csv: Path = SPLITS_CSV) -> tuple[set[str], set[str]]:
    """(train md5 hashes, test md5 hashes) of one seed."""
    df = pd.read_csv(splits_csv, dtype={"md5hash": str})
    col = f"test_seed{seed}"
    if col not in df.columns:
        raise KeyError(f"{splits_csv.name} has no {col}; rerun splits/make_fitzpatrick_splits.py with this seed")
    return set(df.loc[df[col] == 0, "md5hash"]), set(df.loc[df[col] == 1, "md5hash"])


def fitz_subset(full: Fitzpatrick17kDataset, ids: set[str], name: str) -> Fitzpatrick17kDataset:
    """Shallow copy of the external dataset restricted to ``ids`` (its predictions get split = ``name``)."""
    view = copy.copy(full)
    view.rows = full.rows[full.rows["case_id"].isin(ids)].reset_index(drop=True)
    view.name = name
    return view


def train_loader(ds: Dataset, cfg: dict, seed: int) -> DataLoader:
    lc, nw = cfg["loader"], cfg["loader"]["num_workers"]
    return DataLoader(ds, batch_size=lc["batch_size"], shuffle=True, generator=torch.Generator().manual_seed(seed),
                      num_workers=nw, pin_memory=lc["pin_memory"] and torch.cuda.is_available(),
                      persistent_workers=lc["persistent_workers"] and nw > 0, drop_last=False)


def weighted_ce(labels: np.ndarray, n_classes: int, device: torch.device) -> nn.Module:
    return nn.CrossEntropyLoss(weight=class_weights(labels, n_classes).to(device))


# ------------------------------------------------------------------------------------------ train
def train_seed(arm: str, seed: int, cfg: dict, opts: dict, fitz: Fitzpatrick17kDataset, out_dir: Path,
               ckpt: Path, device: torch.device) -> dict:
    seed_everything(seed)
    tc, ib = cfg["train"], cfg["image_baseline"]
    loaders = get_dataloaders(cfg, seed)
    scin_train = loaders["train"].dataset
    classes, k = scin_train.classes, len(scin_train.classes)
    train_ids, test_ids = fitz_folds(seed, opts["splits_csv"])
    if train_ids & test_ids:
        raise AssertionError("Fitzpatrick17k train and test folds overlap")
    fz_rows = fitz.rows[fitz.rows["case_id"].isin(train_ids)]
    fz_train = FitzpatrickTrainView(cfg, fz_rows, seed, len(scin_train.q_cols), len(scin_train.m_cols))
    model = SkinImageBaseline(k, ib["backbone"], tc["pretrained"], ib["top_blocks"], ib["drop_rate"]).to(device)
    fit_args = dict(cfg=cfg, device=device, seed=seed, epochs=opts["epochs"], max_batches=opts["max_batches"])

    if arm == "fitz_pooled":
        pooled = PooledDataset([scin_train, fz_train])
        log.info("seed %d | %s | SCIN train %d + Fitzpatrick17k train %d | class counts %s", seed, arm, len(scin_train),
                 len(fz_train), dict(zip(classes, np.bincount(pooled.labels, minlength=k).tolist())))
        fit = fit_staged(model, {**loaders, "train": train_loader(pooled, cfg, seed)}, weighted_ce(pooled.labels, k, device),
                         image_only_adapt, ckpt=ckpt, out_dir=out_dir, **fit_args)
    elif arm == "fitz_pretrain":
        pre_ckpt, pre_dir = ckpt.with_name(ckpt.stem + "_phaseA.pt"), out_dir / "phaseA"
        pre_dir.mkdir(exist_ok=True)
        pre_ckpt.unlink(missing_ok=True)
        log.info("seed %d | %s phase A | Fitzpatrick17k train %d, model selection on SCIN val", seed, arm, len(fz_train))
        pre = fit_staged(model, {**loaders, "train": train_loader(fz_train, cfg, seed)},
                         weighted_ce(fz_train.labels, k, device), image_only_adapt, ckpt=pre_ckpt, out_dir=pre_dir,
                         **fit_args)
        model.load_state_dict(torch.load(pre_ckpt, map_location=device))  # phase B starts from the best of A
        log.info("seed %d | %s phase B | SCIN train %d (phase A best val macro-F1 %.3f)", seed, arm, len(scin_train),
                 pre["best_val_macro_f1"])
        fit = fit_staged(model, loaders, weighted_ce(scin_train.labels, k, device), image_only_adapt, ckpt=ckpt,
                         out_dir=out_dir, **fit_args)
        fit.update({f"phaseA_{key}": v for key, v in pre.items()})
    else:
        raise ValueError(f"arm must be one of {ARMS}, got {arm!r}")

    model.load_state_dict(torch.load(ckpt, map_location=device))
    loss_fn = weighted_ce(scin_train.labels, k, device)
    frames = []
    for split in ("val", "test"):
        res = evaluate(model, loaders[split], loss_fn, device, image_only_adapt, tc["amp"], opts["max_batches"])
        frames.append(predictions_frame(res, classes, split, seed, 0.0))
        if split == "test":
            test = res
    fz_test = predict_frame(model, fitz_subset(fitz, test_ids, "fitz_test"), seed, device)
    frames.append(fz_test[[c for c in fz_test.columns if not c.startswith(("logit_", "prob_"))]])
    pd.concat(frames, ignore_index=True).to_csv(out_dir / "predictions.csv", index=False)
    fz_f1 = run_e1._fast_metrics(*run_e1.encode(fz_test, classes), k, 15)[0]
    summary = {"seed": seed, **fit, "test_macro_f1": test["macro_f1"], "test_balanced_acc": test["balanced_acc"],
               "fitz_test_macro_f1": fz_f1, "n_test": test["n"], "n_fitz_test": len(fz_test)}
    del model, loaders
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return summary


def run_arm(arm: str, opts: dict, cfg: dict, fitz: Fitzpatrick17kDataset) -> None:
    root = Path(opts["out_root"]) / f"{opts['backbone']}_{arm}"
    (root / "seed_checkpoints").mkdir(parents=True, exist_ok=True)
    (root / "config_used.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for seed in opts["seeds"]:
        out_dir, ckpt = root / f"seed{seed}", root / "seed_checkpoints" / f"{arm}_seed{seed}.pt"
        out_dir.mkdir(exist_ok=True)
        if opts["skip_existing"] and (out_dir / "metrics_summary.csv").exists() and ckpt.exists():
            log.info("%s seed %d already done, skipped", arm, seed)
            continue
        ckpt.unlink(missing_ok=True)  # never resume from another run's weights
        row = {"backbone": opts["backbone"], "arm": arm, **train_seed(arm, seed, cfg, opts, fitz, out_dir, ckpt, device)}
        write_seed_runs(root / "seed_runs.csv", [row])
        harness.main([str(out_dir / "predictions.csv"), "--n-boot", str(opts["n_boot"])])
        log.info("%s seed %d: SCIN test macro-F1 %.3f | Fitzpatrick17k test %.3f", arm, seed, row["test_macro_f1"],
                 row["fitz_test_macro_f1"])


# ---------------------------------------------------------------------------------------- summary
def load_arm(arm: str, opts: dict, split: str) -> pd.DataFrame:
    """Predictions of one arm on SCIN ``test`` or ``fitz_test`` for every seed."""
    seeds = opts["seeds"]
    if arm == REFERENCE and split == "fitz_test":  # zero-shot run of the E1 checkpoints, cut to each seed's fold
        zs = pd.read_csv(str(ZERO_SHOT_CSV).format(run=f"{opts['backbone']}_{opts['balance']}"),
                         dtype={"case_id": str})
        frames = []
        for s in seeds:
            _, test_ids = fitz_folds(s, opts["splits_csv"])
            frames.append(zs[(zs["seed"] == s) & zs["case_id"].isin(test_ids)].assign(split="fitz_test"))
        out = pd.concat(frames, ignore_index=True)
    else:
        d = (run_e1.arm_spec(REFERENCE, opts["backbone"], opts["balance"])["dir"] if arm == REFERENCE
             else Path(opts["out_root"]) / f"{opts['backbone']}_{arm}")
        out = pd.concat([pd.read_csv(d / f"seed{s}" / "predictions.csv", dtype={"case_id": str}) for s in seeds],
                        ignore_index=True)
        out = out[out["split"] == split]
    return out[harness.REQUIRED].assign(arm=arm)


def summarise_split(preds: pd.DataFrame, arms: list[str], opts: dict, classes: list[str]) -> pd.DataFrame:
    arm_table, pair_table = run_e1.summarise(preds, arms, opts["seeds"], classes, opts["n_boot"], 15, 0)
    sub = run_e1.subgroups(preds, arms, opts["seeds"], classes, opts["n_boot"], 0, reference=REFERENCE)
    sub = sub[sub["n_seeds"] > 0]  # Fitzpatrick17k has no Monk tone: drop the empty eMST groups
    return pd.concat([arm_table, pair_table, sub], ignore_index=True)


def markdown(tables: dict[str, pd.DataFrame], arms: list[str], opts: dict) -> str:
    def cell(r):
        return f"{r['mean']:.3f} ± {r['sd']:.3f} [{r['ci_low']:.3f}, {r['ci_high']:.3f}]"

    lines = [f"# E7: adding Fitzpatrick17k training images (seeds {opts['seeds']})", "",
             f"Backbone {opts['backbone']}, class-weighted loss, staged fine-tuning, early stopping on SCIN val. "
             "image_only = E1 photo-only model (SCIN only; on fitz_test it is zero-shot). Each cell: mean ± sd over "
             "seeds [95% seed-stratified case-bootstrap CI]."]
    for split, tab in tables.items():
        title = {"test": "SCIN test split", "fitz_test": "Fitzpatrick17k held-out test fold"}[split]
        lines += ["", f"## {title}", "", "| Arm | Macro-F1 | Balanced accuracy | ECE |", "|---|---|---|---|"]
        a = tab[tab["row_type"] == "arm"]
        for arm in arms:
            r = a[a["arm"] == arm].set_index("metric")
            lines.append(f"| {arm} | {cell(r.loc['macro_f1'])} | {cell(r.loc['balanced_acc'])} | {cell(r.loc['ece'])} |")
        p = tab[tab["row_type"] == "paired"]
        lines += ["", "Paired macro-F1 difference vs image_only (mean [95% CI], seeds better, t-test p, Wilcoxon p):", ""]
        for _, r in p.iterrows():
            lines.append(f"- {r['arm']} - {r['versus']}: {r['mean']:+.3f} [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}], "
                         f"{int(r['a_better_seeds'])}/{int(r['n_seeds'])} seeds, t p = {r['t_test_p']:.3f}, "
                         f"Wilcoxon p = {r['wilcoxon_p']:.3f}")
        sub = tab[tab["row_type"].isin(["arm_group", "arm_class", "paired_group", "paired_class"])]
        lines.append(run_e1.markdown_subgroups(sub, arms, REFERENCE).replace("## By skin tone", "### By skin tone"))
    return "\n".join(lines) + "\n"


def summarise(opts: dict) -> str:
    arms = [REFERENCE] + list(opts["arms"])
    classes = list(load_config(opts["config"])["data"]["classes"])
    tables = {}
    for split in ("test", "fitz_test"):
        preds = pd.concat([load_arm(a, opts, split) for a in arms], ignore_index=True)
        tables[split] = summarise_split(preds, arms, opts, classes).assign(test_set=split)
    out = Path(opts["results_dir"])
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(tables.values(), ignore_index=True).to_csv(out / "e7_summary.csv", index=False, float_format="%.5f")
    text = markdown(tables, arms, opts)
    (out / "e7_table.md").write_text(text, encoding="utf-8")
    log.info("wrote %s", out / "e7_table.md")
    return text


# ------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    ap.add_argument("--backbone", default="efficientnet_b0")
    ap.add_argument("--balance", default="weighted_loss", help="imbalance arm of the E1 reference run")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--splits-csv", type=Path, default=SPLITS_CSV)
    ap.add_argument("--out-root", type=Path, default=ROOT / "runs" / "e7_fitzpatrick")
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results" / "e7")
    ap.add_argument("--epochs", type=int, default=None, help="epochs per stage (default: config)")
    ap.add_argument("--max-batches", type=int, default=None, help="limit batches per epoch (smoke test)")
    ap.add_argument("--num-workers", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--no-train", action="store_true", help="only build the tables from existing runs")
    ap.add_argument("--skip-existing", action="store_true", help="reuse seeds that already have results")
    opts = vars(ap.parse_args(argv))
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = copy.deepcopy(load_config(opts["config"]))
    cfg["image_baseline"]["backbone"] = opts["backbone"]
    if opts["num_workers"] is not None:
        cfg["loader"]["num_workers"] = opts["num_workers"]
    if not opts["no_train"]:
        fitz = Fitzpatrick17kDataset(cfg)
        for arm in opts["arms"]:
            run_arm(arm, opts, cfg, fitz)
    print(summarise(opts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
