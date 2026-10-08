"""PyTorch Dataset and DataLoaders for SCIN (photo + questionnaire + skin-concern category).

One item is one ``case_id``. Image choice:

* train: one image picked at random from the case's available images, redrawn every epoch
  (call ``dataset.set_epoch(epoch)``); augmentation is applied.
* val / test: always the primary image (``image_1_path``); resize + ImageNet normalisation
  only, so evaluation is exactly reproducible.

A missing or unreadable image falls back to another image of the same case; if none can be
read the item gets a black image and ``image_ok = 0`` (never an exception mid-epoch).

Usage::

    python data_loading.py --only-available     # writes sanity_batch.png
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import albumentations as A
import numpy as np
import pandas as pd
import torch
import yaml
from albumentations.pytorch import ToTensorV2
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from utils.seed import seed_everything

log = logging.getLogger("data_loading")
ROOT = Path(__file__).resolve().parent
IMAGE_COLS = ["image_1_path", "image_2_path", "image_3_path"]


def load_config(config_path: str | Path) -> dict:
    return yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))


def build_transform(cfg: dict, train: bool) -> A.Compose:
    size = cfg["data"]["image_size"]
    norm = A.Normalize(mean=cfg["normalize"]["mean"], std=cfg["normalize"]["std"])
    steps: list = [A.Resize(size, size)]  # resize first: all later steps run on small images
    if train:
        aug = cfg["augment"]
        steps += [
            A.HorizontalFlip(p=aug["horizontal_flip"]["p"]),
            A.Affine(scale=tuple(aug["affine"]["scale"]),
                     translate_percent=aug["affine"]["translate_percent"],
                     rotate=aug["affine"]["rotate"], p=aug["affine"]["p"]),
            A.ColorJitter(brightness=aug["color_jitter"]["brightness"],
                          contrast=aug["color_jitter"]["contrast"],
                          saturation=aug["color_jitter"]["saturation"],
                          hue=aug["color_jitter"]["hue"], p=aug["color_jitter"]["p"]),
        ]
    return A.Compose(steps + [norm, ToTensorV2()])


class SCINDataset(Dataset):
    def __init__(self, config_path: str | Path, split: str, seed: int = 0,
                 only_available: bool = False, root: Path = ROOT):
        if split not in ("train", "val", "test"):
            raise ValueError(f"split must be train, val or test, got {split!r}")
        self.cfg = load_config(config_path)
        self.split, self.seed, self.epoch = split, seed, 0
        paths = {k: root / v for k, v in self.cfg["paths"].items()}
        self.images_dir = paths["images_dir"]
        self.classes = list(self.cfg["data"]["classes"])
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}

        splits = json.loads(paths["splits"].read_text(encoding="utf-8"))
        if str(seed) not in splits:
            raise KeyError(f"seed {seed} not in {paths['splits'].name}: {sorted(splits)}")
        ids = splits[str(seed)][split]

        labels = pd.read_csv(paths["labels"], dtype={"case_id": str}).set_index("case_id")
        feats = pd.read_parquet(paths["features"])
        feats.index = feats.index.astype(str)
        cases = pd.read_csv(paths["cases_csv"], dtype=str).set_index("case_id")
        for name, tbl in (("labels", labels), ("features", feats), ("cases", cases)):
            missing = set(ids) - set(tbl.index)
            if missing:
                raise KeyError(f"{len(missing)} split case_ids not found in {name}")

        keep = ~labels.loc[ids, "primary_label"].isin(self.cfg["data"]["drop_labels"]).to_numpy()
        ids = [i for i, k in zip(ids, keep) if k]
        self.image_names = {i: self._image_names(cases.loc[i]) for i in ids}
        if only_available:
            ids = [i for i in ids if any((self.images_dir / n).exists() for n in self.image_names[i])]
        self.case_ids = ids
        log.info("%s: %d cases (seed %d)", split, len(ids), seed)

        self.q_cols = [c for c in feats.columns if c.startswith("f__")]
        self.m_cols = [c for c in feats.columns if c.startswith("m__")]
        self.q_vec = feats.loc[ids, self.q_cols].to_numpy(dtype=np.float32)
        self.q_mask = feats.loc[ids, self.m_cols].to_numpy(dtype=np.float32)
        if np.isnan(self.q_vec).any() or np.isnan(self.q_mask).any():
            raise ValueError("NaN found in questionnaire features")
        self.labels = labels.loc[ids, "primary_label"].map(self.class_to_idx).to_numpy(dtype=np.int64)
        self.efst = pd.to_numeric(labels.loc[ids, "eFST"], errors="coerce").fillna(-1).to_numpy(dtype=np.int64)
        self.transform = build_transform(self.cfg, train=(split == "train"))
        self._warned: set[str] = set()

    def _image_names(self, row: pd.Series) -> list[str]:
        primary = self.cfg["data"]["primary_image_column"]
        cols = [primary] + [c for c in IMAGE_COLS if c != primary]
        return [Path(row[c]).name for c in cols if c in row.index and isinstance(row[c], str)]

    def set_epoch(self, epoch: int) -> None:
        """Changes the random image/augmentation draw of the train split."""
        self.epoch = epoch

    def __len__(self) -> int:
        return len(self.case_ids)

    def _read(self, name: str) -> np.ndarray | None:
        try:
            with Image.open(self.images_dir / name) as im:
                return np.asarray(im.convert("RGB"))
        except (FileNotFoundError, OSError, ValueError) as e:
            if name not in self._warned:
                self._warned.add(name)
                log.warning("cannot read image %s (%s)", name, type(e).__name__)
            return None

    def _load_image(self, idx: int, rng: np.random.Generator) -> tuple[np.ndarray, bool]:
        names = self.image_names[self.case_ids[idx]]
        if self.split == "train" and len(names) > 1:
            first = int(rng.integers(len(names)))   # random image per case per epoch
            names = [names[first]] + [n for j, n in enumerate(names) if j != first]
        for n in names:                             # val/test: primary image first, always
            img = self._read(n)
            if img is not None:
                return img, True
        size = self.cfg["data"]["image_size"]
        return np.zeros((size, size, 3), dtype=np.uint8), False

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        # Per-item RNG from (seed, epoch, idx): same draw whatever the number of workers.
        rng = np.random.default_rng([self.seed, self.epoch, idx])
        img, ok = self._load_image(idx, rng)
        if self.split == "train":
            self.transform.set_random_seed(int(rng.integers(2**31 - 1)))
        return {
            "image": self.transform(image=img)["image"],
            "q_vec": torch.from_numpy(self.q_vec[idx].copy()),
            "q_mask": torch.from_numpy(self.q_mask[idx].copy()),
            "label": torch.tensor(self.labels[idx]),
            "eFST": torch.tensor(self.efst[idx]),
            "case_id": torch.tensor(int(self.case_ids[idx]), dtype=torch.int64),
            "image_ok": torch.tensor(int(ok)),
        }


def get_dataloaders(config_path: str | Path, seed: int = 0, split: str | None = None,
                    only_available: bool = False) -> DataLoader | dict[str, DataLoader]:
    """DataLoaders for train, val and test (dict), or one loader if ``split`` is given."""
    cfg = load_config(config_path)
    lc = cfg["loader"]
    out = {}
    for name in ([split] if split else ["train", "val", "test"]):
        ds = SCINDataset(config_path, name, seed, only_available)
        gen = torch.Generator().manual_seed(seed)
        nw = lc["num_workers"]
        out[name] = DataLoader(
            ds, batch_size=lc["batch_size"], shuffle=(name == "train"), generator=gen,
            num_workers=nw, pin_memory=lc["pin_memory"] and torch.cuda.is_available(),
            persistent_workers=lc["persistent_workers"] and nw > 0, drop_last=False)
    return out[split] if split else out


def save_sanity_grid(batch: dict, classes: list[str], cfg: dict, path: Path, n: int = 16) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mean = torch.tensor(cfg["normalize"]["mean"]).view(3, 1, 1)
    std = torch.tensor(cfg["normalize"]["std"]).view(3, 1, 1)
    n = min(n, len(batch["label"]))
    cols = 4
    fig, axes = plt.subplots((n + cols - 1) // cols, cols, figsize=(3 * cols, 3.3 * ((n + cols - 1) // cols)))
    for ax in np.atleast_1d(axes).ravel():
        ax.axis("off")
    for i, ax in enumerate(np.atleast_1d(axes).ravel()[:n]):
        img = (batch["image"][i] * std + mean).clamp(0, 1).permute(1, 2, 0).numpy()
        ax.imshow(img)
        efst = int(batch["eFST"][i])
        ax.set_title(f"{classes[int(batch['label'][i])]}\neFST {efst if efst > 0 else 'NA'} | "
                     f"missing {int(batch['q_mask'][i].sum())}/{len(batch['q_mask'][i])} "
                     f"| id ..{str(int(batch['case_id'][i]))[-4:]}", fontsize=8)
    fig.suptitle("Augmented training batch (train split)", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Fetch one training batch and save a sanity grid.")
    p.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=ROOT / "sanity_batch.png")
    p.add_argument("--only-available", action="store_true",
                   help="skip cases whose images are not downloaded yet")
    p.add_argument("--num-workers", type=int, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    seed_everything(args.seed)
    cfg = load_config(args.config)
    if args.num_workers is not None:
        cfg["loader"]["num_workers"] = args.num_workers
        tmp = args.config.with_name("_tmp_sanity.yaml")
        tmp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        args.config = tmp
    try:
        loader = get_dataloaders(args.config, args.seed, "train", args.only_available)
        batch = next(iter(loader))
    finally:
        tmp_file = args.config.with_name("_tmp_sanity.yaml")
        if tmp_file.exists():
            tmp_file.unlink()
    for k, v in batch.items():
        log.info("%-8s %s %s", k, tuple(v.shape), v.dtype)
    log.info("images readable: %d/%d", int(batch["image_ok"].sum()), len(batch["image_ok"]))
    save_sanity_grid(batch, loader.dataset.classes, cfg, args.out)
    log.info("saved %s", args.out)
