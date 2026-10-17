"""Near-duplicate groups and per-seed train/test folds for the mapped Fitzpatrick17k images (E7).

Fitzpatrick17k was collected from two online atlases and holds many near-duplicates: the same
photo re-uploaded, resized, re-compressed, mirrored or re-cropped, and several photos of the same
patient. If one of them is in training and another in the test fold, the test score is too high
(leakage). Exact MD5 matching misses these copies, so two similarity checks link images:

* difference hash (dHash, 256 bits): the image is turned to greyscale and shrunk to 17 x 16 pixels;
  every bit says whether a pixel is brighter than its right neighbour. Copies of one photo differ in
  few bits; the Hamming distance (number of differing bits, 0-256) measures it. Linked if
  <= ``--max-hash-distance`` (default 20; above about 25 bits, pairs with different diagnoses appear).
* embedding similarity: cosine similarity (1 = same direction) of ImageNet EfficientNet-B0 features
  (no skin training, so no label information). Linked if >= ``--min-cosine`` (default 0.88). A visual
  check of sampled pairs found the same patient or lesion in nearly all pairs above 0.88 (including
  mirrored copies), and unrelated photos becoming common below about 0.87.

Linked images form one group (union-find), and whole groups go to one side of the split. For every
split seed (0-9 by default) ``StratifiedGroupKFold`` (5 folds, shuffled with the seed) puts about
20% of the groups in the test fold, keeping the category mix as equal as possible; the other 80%
may be used for training. The SCIN splits are not touched.

Output ``splits/fitzpatrick17k_splits.csv`` (no images, only ids): md5hash, label, eFST, dup_group,
group_size, then ``test_seed<k>`` = 1 if the image is in the test fold of seed k.

Usage::

    python splits/make_fitzpatrick_splits.py
    python splits/make_fitzpatrick_splits.py --min-cosine 0.9 --seeds 0 1 2 3 4
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_loading import build_transform, load_config  # noqa: E402
from external_datasets import DEFAULT_ROOTS, mapping_report  # noqa: E402

log = logging.getLogger("make_fitzpatrick_splits")
OUT = ROOT / "splits" / "fitzpatrick17k_splits.csv"


def dhash_bits(path: Path, size: int = 16) -> np.ndarray:
    """size*size-bit difference hash: bit = pixel brighter than its right neighbour (packed to bytes)."""
    with Image.open(path) as im:
        g = np.asarray(im.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS), dtype=np.int16)
    return np.packbits((g[:, 1:] > g[:, :-1]).ravel())


def hamming_matrix(packed: np.ndarray, chunk: int = 256) -> np.ndarray:
    """All pairwise Hamming distances between packed bit rows (n, bytes) -> (n, n)."""
    n = len(packed)
    out = np.zeros((n, n), dtype=np.int16)
    for i in range(0, n, chunk):
        out[i:i + chunk] = np.bitwise_count(packed[i:i + chunk, None, :] ^ packed[None, :, :]).sum(-1)
    return out


@torch.no_grad()
def embeddings(paths: list[Path], cfg: dict, backbone: str = "efficientnet_b0", batch: int = 64) -> np.ndarray:
    """L2-normalised ImageNet features (val preprocessing of the SCIN pipeline)."""
    import timm

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = timm.create_model(backbone, pretrained=True, num_classes=0).to(device).eval()
    tf = build_transform(cfg, train=False)
    feats = []
    for i in range(0, len(paths), batch):
        imgs = []
        for p in paths[i:i + batch]:
            with Image.open(p) as im:
                imgs.append(tf(image=np.asarray(im.convert("RGB")))["image"])
        feats.append(torch.nn.functional.normalize(model(torch.stack(imgs).to(device)).float(), dim=1).cpu())
    return torch.cat(feats).numpy()


def group_ids(n: int, pairs) -> np.ndarray:
    """Union-find over the linked pairs; returns one group number per item (0..n_groups-1)."""
    parent = np.arange(n)

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in pairs:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)])
    return np.unique(roots, return_inverse=True)[1]


def linked_pairs(hamming: np.ndarray, cosine: np.ndarray, max_hash: int, min_cos: float) -> list[tuple[int, int]]:
    """Pairs (i < j) that are near-identical by hash or very similar by embedding."""
    iu = np.triu_indices(len(hamming), 1)
    keep = (hamming[iu] <= max_hash) | (cosine[iu] >= min_cos)
    return list(zip(iu[0][keep].tolist(), iu[1][keep].tolist()))


def test_folds(labels: np.ndarray, groups: np.ndarray, seed: int, n_folds: int = 5) -> np.ndarray:
    """1 for the items in the test fold (first fold of a shuffled StratifiedGroupKFold), else 0."""
    cv = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    _, test = next(iter(cv.split(np.zeros(len(labels)), labels, groups)))
    mask = np.zeros(len(labels), dtype=np.int8)
    mask[test] = 1
    return mask


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.yaml")
    ap.add_argument("--label-map", type=Path, default=ROOT / "labels" / "label_map.yaml")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOTS["fitzpatrick17k"])
    ap.add_argument("--max-hash-distance", type=int, default=20, help="256-bit dHash distance that links two images")
    ap.add_argument("--min-cosine", type=float, default=0.88, help="embedding cosine similarity that links two images")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(range(10)))
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config(args.config)
    rep = mapping_report("fitzpatrick17k", args.root, args.label_map, list(cfg["data"]["classes"]))
    rows = rep[rep["status"] == "mapped"].reset_index(drop=True)
    paths = list(rows["image_path"])
    log.info("hashing and embedding %d mapped images", len(rows))
    ham = hamming_matrix(np.stack([dhash_bits(p) for p in paths]))
    emb = embeddings(paths, cfg)
    pairs = linked_pairs(ham, emb @ emb.T, args.max_hash_distance, args.min_cosine)
    groups = group_ids(len(rows), pairs)
    sizes = np.bincount(groups)
    lab = rows["label"].to_numpy()
    cross = sum(lab[i] != lab[j] for i, j in pairs)
    log.info("%d linked pairs (%d with different categories); %d groups, %d images in groups of 2+, "
             "largest group %d", len(pairs), cross, len(sizes), int(sizes[sizes > 1].sum()), sizes.max())

    out = pd.DataFrame({"md5hash": rows["case_id"], "label": lab, "eFST": rows["eFST"],
                        "dup_group": groups, "group_size": sizes[groups]})
    for s in args.seeds:
        out[f"test_seed{s}"] = test_folds(lab, groups, s, args.n_folds)
        test = out[f"test_seed{s}"] == 1
        if set(out.loc[test, "dup_group"]) & set(out.loc[~test, "dup_group"]):
            raise AssertionError(f"seed {s}: a duplicate group is on both sides of the split")
        log.info("seed %d: test %d / train %d | test per class %s", s, test.sum(), (~test).sum(),
                 out.loc[test, "label"].value_counts().to_dict())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    log.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
