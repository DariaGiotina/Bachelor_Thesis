"""External image-only test sets (DDI, Fitzpatrick17k) and zero-shot evaluation of the SCIN image model.

Neither dataset has questionnaire answers, so only the photo-only model is tested. Each diagnosis is
mapped to the SCIN target categories with ``labels/label_map.yaml`` (its ``mapping`` plus the
per-dataset ``external_aliases``), after normalisation: case-insensitive, '-' and '_' read as spaces.
Every metadata row gets one status, written to ``<dataset>_mapping_report.csv``:

  mapped          diagnosis -> a target category; kept
  excluded_class  diagnosis is listed under a non-target category (e.g. 'excluded'); dropped
  unmapped        diagnosis matches nothing (never guessed); dropped, listed in the log
  qc_wrong_label  Fitzpatrick17k quality check says "wrongly labelled"; dropped
  missing_image   no image file on disk; dropped

Skin tone: Fitzpatrick17k ``fitzpatrick_scale`` 1-6 (-1 = unknown) is used as eFST; DDI ``skin_tone``
12 / 34 / 56 becomes 1 / 3 / 5, i.e. the groups I-II / III-IV / V-VI of evaluate.py (the raw value
is kept in ``tone_raw``). Neither dataset has a Monk tone (eMST empty).

``predict`` runs every SCIN image-only checkpoint (one per split seed) over the kept images with the
SCIN val/test preprocessing (letterbox + ImageNet normalisation) and writes ``external_eval.csv`` in
the evaluate.py format (split = dataset name, seed = SCIN seed) plus ``logit_<class>`` and
``prob_<class>`` columns; evaluate.py then writes the metrics next to it.

Expected layout (git-ignored, not redistributed):
  data/ddi/ddi_metadata.csv + images (in data/ddi/ or data/ddi/images/), from Stanford AIMI
  data/fitzpatrick17k/fitzpatrick17k.csv + images/<md5hash>.jpg (``--download-fitzpatrick``)

Usage::

    python external_datasets.py --download-fitzpatrick        # mapped Fitzpatrick17k images only
    python external_datasets.py --checkpoints "runs/e1_image_only/efficientnet_b0_weighted_loss/seed_checkpoints/*.pt"
    python external_datasets.py --datasets fitzpatrick17k --report-only
"""
from __future__ import annotations

import argparse
import copy
import glob
import logging
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from PIL import Image
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import evaluate as harness  # noqa: E402
from data_loading import ROOT, build_transform, load_config  # noqa: E402
from models.image_model import SkinImageBaseline  # noqa: E402

log = logging.getLogger("external_datasets")
DATASETS = ("ddi", "fitzpatrick17k")
DEFAULT_ROOTS = {"ddi": ROOT / "data" / "ddi", "fitzpatrick17k": ROOT / "data" / "fitzpatrick17k"}
DDI_TONE = {12: 1, 34: 3, 56: 5}  # DDI groups -> one FST value inside the same evaluate.py group


# ---------------------------------------------------------------------------------- label mapping
def normalise(name) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", str(name))).strip().casefold()


class LabelMapper:
    """Raw external diagnosis -> (SCIN target category or None, status)."""

    def __init__(self, label_map: Path, dataset: str, targets: list[str]):
        lm = yaml.safe_load(Path(label_map).read_text(encoding="utf-8"))
        self.targets = list(targets)
        self.lookup: dict[str, str] = {}
        for cls, names in lm["mapping"].items():
            for n in names:
                self.lookup[normalise(n)] = cls
        for cls, names in (lm.get("external_aliases", {}).get(dataset) or {}).items():
            if cls not in lm["classes"]:
                raise ValueError(f"external_aliases.{dataset} uses unknown category {cls!r}")
            for n in names:
                if self.lookup.get(normalise(n), cls) != cls:
                    raise ValueError(f"alias {n!r} conflicts with the SCIN mapping")
                self.lookup[normalise(n)] = cls

    def __call__(self, raw) -> tuple[str | None, str]:
        if raw is None or (isinstance(raw, float) and np.isnan(raw)) or not str(raw).strip():
            return None, "unmapped"
        cls = self.lookup.get(normalise(raw))
        if cls is None:
            return None, "unmapped"
        return (cls, "mapped") if cls in self.targets else (None, "excluded_class")


# ------------------------------------------------------------------------------- metadata readers
def _find(root: Path, name: str, subdirs=("", "images")) -> Path | None:
    for sub in subdirs:
        p = root / sub / name
        if p.exists():
            return p
    return None


def read_ddi(root: Path) -> pd.DataFrame:
    """DDI ``ddi_metadata.csv``: DDI_file, skin_tone (12/34/56), disease."""
    meta = pd.read_csv(root / "ddi_metadata.csv")
    meta = meta.drop(columns=[c for c in meta.columns if c.startswith("Unnamed")])
    for col in ("DDI_file", "skin_tone", "disease"):
        if col not in meta.columns:
            raise KeyError(f"ddi_metadata.csv lacks column {col!r} (has {list(meta.columns)})")
    tone = pd.to_numeric(meta["skin_tone"], errors="coerce")
    return pd.DataFrame({
        "case_id": meta["DDI_file"].astype(str).str.rsplit(".", n=1).str[0],
        "image_path": [_find(root, f) for f in meta["DDI_file"].astype(str)],
        "raw_label": meta["disease"], "tone_raw": tone,
        "eFST": tone.map(DDI_TONE).astype("Int64"), "qc_wrong": False})


def read_fitzpatrick17k(root: Path) -> pd.DataFrame:
    """Fitzpatrick17k CSV: md5hash, fitzpatrick_scale (1-6, -1 unknown), label, qc, url."""
    meta = pd.read_csv(root / "fitzpatrick17k.csv")
    tone = pd.to_numeric(meta["fitzpatrick_scale"], errors="coerce")
    return pd.DataFrame({
        "case_id": meta["md5hash"].astype(str),
        "image_path": [_find(root, f"{h}.jpg") for h in meta["md5hash"].astype(str)],
        "raw_label": meta["label"], "tone_raw": tone,
        "eFST": tone.where(tone.between(1, 6)).astype("Int64"),
        "qc_wrong": meta["qc"].astype(str).str.startswith("3"), "url": meta["url"]})


READERS = {"ddi": read_ddi, "fitzpatrick17k": read_fitzpatrick17k}


def mapping_report(dataset: str, root: Path, label_map: Path, targets: list[str]) -> pd.DataFrame:
    """One row per metadata row with its target category and status (see module docstring)."""
    df = READERS[dataset](Path(root))
    mapper = LabelMapper(label_map, dataset, targets)
    mapped = [mapper(r) for r in df["raw_label"]]
    df["label"] = [m[0] for m in mapped]
    df["status"] = [m[1] for m in mapped]
    df.loc[(df["status"] == "mapped") & df["qc_wrong"], "status"] = "qc_wrong_label"
    df.loc[(df["status"] == "mapped") & df["image_path"].isna(), "status"] = "missing_image"
    if df["case_id"].duplicated().any():
        raise ValueError(f"{dataset}: duplicate case ids")
    return df


def log_report(dataset: str, rep: pd.DataFrame) -> None:
    log.info("%s: %d rows | %s", dataset, len(rep), rep["status"].value_counts().to_dict())
    kept = rep[rep["status"] == "mapped"]
    log.info("%s kept per class: %s", dataset, kept["label"].value_counts().to_dict())
    log.info("%s kept per eFST: %s", dataset, kept["eFST"].value_counts(dropna=False).sort_index().to_dict())
    top = rep.loc[rep["status"] == "unmapped", "raw_label"].value_counts().head(15)
    if len(top):
        log.info("%s most frequent unmapped diagnoses (dropped): %s", dataset, top.to_dict())


# ---------------------------------------------------------------------------------------- dataset
class ExternalImageDataset(Dataset):
    """Kept rows of an external set; items look like SCIN items (image, label, eFST, eMST, case_id).

    An unreadable image gives a black image and ``image_ok = 0`` instead of an exception.
    """

    name = "external"

    def __init__(self, config: str | Path | dict, root: Path | None = None,
                 label_map: Path = ROOT / "labels" / "label_map.yaml"):
        self.cfg = load_config(config)
        self.classes = list(self.cfg["data"]["classes"])
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}
        self.report = mapping_report(self.name, root or DEFAULT_ROOTS[self.name], label_map, self.classes)
        self.rows = self.report[self.report["status"] == "mapped"].reset_index(drop=True)
        self.transform = build_transform(self.cfg, train=False)
        self._warned: set[str] = set()

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> dict:
        row = self.rows.iloc[idx]
        size = self.cfg["data"]["image_size"]
        try:
            with Image.open(row["image_path"]) as im:
                img, ok = np.asarray(im.convert("RGB")), 1
        except (OSError, ValueError) as e:
            if row["case_id"] not in self._warned:
                self._warned.add(row["case_id"])
                log.warning("%s: cannot read %s (%s)", self.name, row["image_path"], type(e).__name__)
            img, ok = np.zeros((size, size, 3), dtype=np.uint8), 0
        efst = row["eFST"]
        return {"image": self.transform(image=img)["image"],
                "label": torch.tensor(self.class_to_idx[row["label"]]),
                "eFST": torch.tensor(int(efst) if pd.notna(efst) else -1),
                "eMST": torch.tensor(-1), "case_id": str(row["case_id"]), "image_ok": torch.tensor(ok)}


class DDIDataset(ExternalImageDataset):
    name = "ddi"


class Fitzpatrick17kDataset(ExternalImageDataset):
    name = "fitzpatrick17k"


DATASET_CLASSES = {"ddi": DDIDataset, "fitzpatrick17k": Fitzpatrick17kDataset}


# ------------------------------------------------------------------------------------- inference
@torch.no_grad()
def predict_frame(model: torch.nn.Module, ds: ExternalImageDataset, seed: int, device: torch.device,
                  batch_size: int = 64, num_workers: int = 0) -> pd.DataFrame:
    """Per-image predictions in the evaluate.py format, with logits and probabilities."""
    model.eval()
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=num_workers,
                        pin_memory=device.type == "cuda")
    logits, efst, ids, ok, labels = [], [], [], [], []
    for batch in loader:
        with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
            out = model(image=batch["image"].to(device, non_blocking=True))
        logits.append(out.float().cpu())
        efst.append(batch["eFST"].numpy())
        labels.append(batch["label"].numpy())
        ids += list(batch["case_id"])
        ok.append(batch["image_ok"].numpy())
    z = torch.cat(logits)
    prob = z.softmax(1)
    conf, pred = prob.max(1)
    classes, efst = ds.classes, np.concatenate(efst)
    df = pd.DataFrame({
        "case_id": ids, "split": ds.name, "true_label": [classes[i] for i in np.concatenate(labels)],
        "pred_label": [classes[i] for i in pred.numpy()], "confidence": conf.numpy().round(6),
        "eFST": pd.Series(efst).where(lambda s: s > 0).astype("Int64"), "eMST": pd.array([pd.NA] * len(ids), "Int64"),
        "seed": seed, "missing_pct": 0.0, "image_ok": np.concatenate(ok),
        "tone_raw": ds.rows["tone_raw"].to_numpy(), "raw_label": ds.rows["raw_label"].to_numpy()})
    for j, c in enumerate(classes):
        df[f"logit_{c}"] = z[:, j].numpy().round(5)
        df[f"prob_{c}"] = prob[:, j].numpy().round(6)
    return df


def seed_of(path: Path) -> int:
    m = re.search(r"seed(\d+)", path.stem)
    if not m:
        raise ValueError(f"cannot read the SCIN seed from {path.name} (expected ...seed<k>.pt)")
    return int(m.group(1))


def run_backbone(ckpt: Path) -> str:
    """Backbone recorded by run_image_only.py next to the checkpoints (runs/.../<exp>/config_used.yaml)."""
    used = ckpt.parent.parent / "config_used.yaml"
    if not used.exists():
        raise FileNotFoundError(f"{used} not found; pass --backbone")
    return yaml.safe_load(used.read_text(encoding="utf-8"))["image_baseline"]["backbone"]


def run_external_eval(cfg: dict, checkpoints: list[Path], backbone: str, datasets: dict, out_dir: Path,
                      n_boot: int, num_workers: int = 0) -> Path:
    """Every checkpoint on every dataset -> external_eval.csv, then evaluate.py on it."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ib, frames = cfg["image_baseline"], []
    for ckpt in sorted(checkpoints, key=seed_of):
        model = SkinImageBaseline(len(cfg["data"]["classes"]), backbone, pretrained=False,
                                  top_blocks=ib["top_blocks"], drop_rate=ib["drop_rate"]).to(device)
        model.load_state_dict(torch.load(ckpt, map_location=device))
        for name, ds in datasets.items():
            df = predict_frame(model, ds, seed_of(ckpt), device, num_workers=num_workers)
            log.info("%s seed %d: %d images, accuracy %.3f (unreadable %d)", name, seed_of(ckpt), len(df),
                     (df["true_label"] == df["pred_label"]).mean(), int((df["image_ok"] == 0).sum()))
            frames.append(df)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "external_eval.csv"
    pd.concat(frames, ignore_index=True).to_csv(path, index=False)
    harness.main([str(path), "--n-boot", str(n_boot)])
    return path


# ------------------------------------------------------------------------------- image download
def download_fitzpatrick17k(root: Path, label_map: Path, targets: list[str], timeout: float = 20,
                            retries: int = 2) -> None:
    """Download the images of the mapped Fitzpatrick17k rows to images/<md5hash>.jpg (skips existing).

    Images come from the atlas URLs in the CSV (some are offline); they are for research use and are
    never redistributed.
    """
    import requests

    rep = mapping_report("fitzpatrick17k", root, label_map, targets)
    todo = rep[rep["status"].isin(["mapped", "missing_image"])]
    (root / "images").mkdir(parents=True, exist_ok=True)
    got, failed = 0, []
    for k, (_, r) in enumerate(todo.iterrows(), 1):
        if k % 250 == 0:
            log.info("fitzpatrick17k: %d/%d checked, %d downloaded, %d failed", k, len(todo), got, len(failed))
        dest = root / "images" / f"{r['case_id']}.jpg"
        if dest.exists():
            continue
        for attempt in range(retries + 1):
            try:
                resp = requests.get(r["url"], timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (research)"})
                if 400 <= resp.status_code < 500:  # gone from the source site: retrying cannot help
                    failed.append((r["case_id"], f"HTTP {resp.status_code}"))
                    break
                resp.raise_for_status()
                tmp = dest.with_suffix(".part")
                tmp.write_bytes(resp.content)
                with Image.open(tmp) as im:  # keep only files that are real images
                    im.verify()
                tmp.replace(dest)
                got += 1
                break
            except Exception as e:  # noqa: BLE001 - any network/decoding failure is logged, not fatal
                dest.with_suffix(".part").unlink(missing_ok=True)
                if attempt == retries:
                    failed.append((r["case_id"], type(e).__name__))
                else:
                    time.sleep(1 + attempt)
    log.info("fitzpatrick17k: downloaded %d, failed %d, already present %d", got, len(failed),
             len(todo) - got - len(failed))
    if failed:
        pd.DataFrame(failed, columns=["case_id", "error"]).to_csv(root / "download_failures.csv", index=False)


# ------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--label-map", type=Path, default=ROOT / "labels" / "label_map.yaml")
    ap.add_argument("--datasets", nargs="+", choices=DATASETS, default=list(DATASETS))
    ap.add_argument("--ddi-root", type=Path, default=DEFAULT_ROOTS["ddi"])
    ap.add_argument("--fitzpatrick-root", type=Path, default=DEFAULT_ROOTS["fitzpatrick17k"])
    ap.add_argument("--checkpoints", default=str(ROOT / "runs" / "e1_image_only" / "efficientnet_b0_weighted_loss"
                                                 / "seed_checkpoints" / "img_only_seed*.pt"),
                    help="glob of SCIN image-only checkpoints (seed read from the file name)")
    ap.add_argument("--backbone", default=None,
                    help="backbone of the checkpoints (default: read from the run's config_used.yaml)")
    ap.add_argument("--out-dir", type=Path, default=None, help="default: runs/external_eval/<checkpoint run>")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--report-only", action="store_true", help="only write the mapping reports")
    ap.add_argument("--download-fitzpatrick", action="store_true", help="download mapped Fitzpatrick17k images")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = copy.deepcopy(load_config(args.config))
    targets = list(cfg["data"]["classes"])
    roots = {"ddi": args.ddi_root, "fitzpatrick17k": args.fitzpatrick_root}
    if args.download_fitzpatrick:
        download_fitzpatrick17k(roots["fitzpatrick17k"], args.label_map, targets)
        return 0

    ckpts = [Path(p) for p in glob.glob(args.checkpoints)]
    out_dir = args.out_dir or ROOT / "runs" / "external_eval" / (ckpts[0].parent.parent.name if ckpts else "report")
    out_dir.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name in args.datasets:
        meta = roots[name] / ("ddi_metadata.csv" if name == "ddi" else "fitzpatrick17k.csv")
        if not meta.exists():
            log.warning("%s: %s not found, dataset skipped", name, meta)
            continue
        ds = DATASET_CLASSES[name](cfg, roots[name], args.label_map)
        ds.report.drop(columns=["url"], errors="ignore").to_csv(out_dir / f"{name}_mapping_report.csv", index=False)
        log_report(name, ds.report)
        if len(ds):
            datasets[name] = ds
        else:
            log.warning("%s: no usable images, dataset skipped", name)
    if args.report_only:
        return 0
    if not datasets:
        log.error("no external dataset with usable images")
        return 1
    if not ckpts:
        log.error("no checkpoints match %s", args.checkpoints)
        return 1
    backbone = args.backbone or run_backbone(ckpts[0])
    log.info("checkpoints: %d, backbone %s", len(ckpts), backbone)
    run_external_eval(cfg, ckpts, backbone, datasets, out_dir, args.n_boot, args.num_workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
