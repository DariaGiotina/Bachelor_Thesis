"""Download SCIN image files listed in scin_cases.csv into data/scin/images/.

Usage::

    python scripts/download_scin_images.py --limit 64            # first 64 cases, primary image
    python scripts/download_scin_images.py --all-images          # every image (about 10 GB)

SCIN is released under the SCIN Data Use License; the images stay in the git-ignored data folder
and must not be redistributed or used to re-identify anyone.
"""
from __future__ import annotations

import argparse
import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

GCS_BASE = "https://storage.googleapis.com/dx-scin-public-data"
ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("download_scin_images")


def fetch(rel_path: str, out_dir: Path) -> bool:
    target = out_dir / Path(rel_path).name
    if target.exists() and target.stat().st_size > 0:
        return True
    try:
        urllib.request.urlretrieve(f"{GCS_BASE}/{rel_path}", target.with_suffix(".part"))
        target.with_suffix(".part").replace(target)
        return True
    except OSError as e:
        log.warning("failed %s (%s)", rel_path, e)
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cases-csv", type=Path, default=ROOT / "data" / "scin" / "scin_cases.csv")
    p.add_argument("--out-dir", type=Path, default=ROOT / "data" / "scin" / "images")
    p.add_argument("--limit", type=int, default=None, help="only the first N cases")
    p.add_argument("--all-images", action="store_true", help="also image_2 and image_3")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cases = pd.read_csv(args.cases_csv, dtype=str)
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
