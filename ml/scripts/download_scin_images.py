"""Download SCIN image files listed in scin_cases.csv into data/scin/images/.

Usage::

    python scripts/download_scin_images.py --limit 64            # first 64 cases, primary image
    python scripts/download_scin_images.py --all-images          # every image (about 10 GB)
    python scripts/download_scin_images.py --used-only --all-images   # only cases used for training (about 3.9 GB)

SCIN is released under the SCIN Data Use License; the images stay in the git-ignored data folder
and must not be redistributed or used to re-identify anyone.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

GCS_BASE = "https://storage.googleapis.com/dx-scin-public-data"
ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("download_scin_images")


def fetch(rel_path: str, out_dir: Path, retries: int = 3) -> bool:
    target = out_dir / Path(rel_path).name
    if target.exists() and target.stat().st_size > 0:
        return True
    part = target.with_suffix(".part")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(f"{GCS_BASE}/{rel_path}", timeout=60) as resp, open(part, "wb") as f:
                shutil.copyfileobj(resp, f)
            part.replace(target)
            return True
        except OSError as e:
            log.warning("attempt %d failed %s (%s)", attempt, rel_path, e)
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cases-csv", type=Path, default=ROOT / "data" / "scin" / "scin_cases.csv")
    p.add_argument("--out-dir", type=Path, default=ROOT / "data" / "scin" / "images")
    p.add_argument("--limit", type=int, default=None, help="only the first N cases")
    p.add_argument("--all-images", action="store_true", help="also image_2 and image_3")
    p.add_argument("--used-only", action="store_true",
                   help="only cases whose primary_label is not in drop_labels of configs/base.yaml")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cases = pd.read_csv(args.cases_csv, dtype=str)
    if args.used_only:
        import yaml
        cfg = yaml.safe_load((ROOT / "configs" / "base.yaml").read_text(encoding="utf-8"))
        labels = pd.read_csv(ROOT / "labels" / "scin_labels.csv", dtype={"case_id": str})
        keep = labels.loc[~labels["primary_label"].isin(cfg["data"]["drop_labels"]), "case_id"]
        cases = cases[cases["case_id"].isin(keep)]
    if args.limit:
        cases = cases.head(args.limit)
    cols = ["image_1_path", "image_2_path", "image_3_path"] if args.all_images else ["image_1_path"]
    paths = pd.Series(cases[cols].to_numpy().ravel()).dropna().tolist()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(args.workers) as ex:
        ok = sum(ex.map(lambda r: fetch(r, args.out_dir), paths))
    log.info("downloaded or present: %d/%d -> %s", ok, len(paths), args.out_dir)
    return 0 if ok == len(paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
