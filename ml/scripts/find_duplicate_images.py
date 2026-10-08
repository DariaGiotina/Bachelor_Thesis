"""Find SCIN cases that share an identical image file (same MD5 hash).

Some contributors submitted the same photos in more than one case. Such cases must stay in the
same split, otherwise a test photo is also seen in training (leakage). Writes
``splits/duplicate_image_groups.csv`` with one row per case that belongs to a duplicate group:
``case_id, dup_group, n_cases``.

Only images present in ``data/scin/images`` are hashed (run the downloader first); the log reports
how many of the used cases were covered.

Usage::

    python scripts/find_duplicate_images.py
"""
from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMAGE_COLS = ["image_1_path", "image_2_path", "image_3_path"]
log = logging.getLogger("find_duplicate_images")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def duplicate_groups(pairs: pd.DataFrame) -> pd.DataFrame:
    """pairs: columns case_id, md5. Cases linked through any shared hash form one group (union-find)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for _, g in pairs.groupby("md5"):
        ids = g["case_id"].unique()
        for other in ids[1:]:
            parent[find(other)] = find(ids[0])
    groups = pd.DataFrame({"case_id": list(parent)})
    groups["root"] = groups["case_id"].map(find)
    groups["n_cases"] = groups.groupby("root")["case_id"].transform("size")
    groups = groups[groups["n_cases"] > 1]
    # stable, readable group ids
    order = {r: f"dup{i:03d}" for i, r in enumerate(sorted(groups["root"].unique()))}
    groups["dup_group"] = groups["root"].map(order)
    return groups[["case_id", "dup_group", "n_cases"]].sort_values(["dup_group", "case_id"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cases-csv", type=Path, default=ROOT / "data" / "scin" / "scin_cases.csv")
    p.add_argument("--images-dir", type=Path, default=ROOT / "data" / "scin" / "images")
    p.add_argument("--labels", type=Path, default=ROOT / "labels" / "scin_labels.csv")
    p.add_argument("--out", type=Path, default=ROOT / "splits" / "duplicate_image_groups.csv")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cases = pd.read_csv(args.cases_csv, dtype=str)
    rows, missing = [], 0
    for cid, *paths in cases[["case_id", *IMAGE_COLS]].itertuples(index=False):
        for rel in paths:
            if not isinstance(rel, str):
                continue
            f = args.images_dir / Path(rel).name
            if f.exists():
                rows.append((cid, md5(f)))
            else:
                missing += 1
    pairs = pd.DataFrame(rows, columns=["case_id", "md5"])
    groups = duplicate_groups(pairs)

    labels = pd.read_csv(args.labels, dtype={"case_id": str})
    used = set(labels.loc[labels["primary_label"] != "excluded", "case_id"])
    hashed = set(pairs["case_id"])
    log.info("hashed %d images of %d cases (%d image files not on disk); used cases covered: %d/%d",
             len(pairs), len(hashed), missing, len(used & hashed), len(used))
    log.info("duplicate groups: %d covering %d cases", groups["dup_group"].nunique(), len(groups))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    groups.to_csv(args.out, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
