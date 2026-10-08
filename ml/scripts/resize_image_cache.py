"""Write downscaled copies of the SCIN images to speed up training.

Decoding the original photos (about 1 MB PNG, up to 1080 px) dominates the epoch time. The model
only sees 224 px, so a lossless PNG copy whose longest side is ``--max-side`` (default 448, twice
the input size) gives the same model input at a fraction of the cost. The aspect ratio is kept;
images already smaller are copied unchanged. ``data_loading.py`` reads the cache first and falls
back to the originals.

Usage::

    python scripts/resize_image_cache.py
"""
from __future__ import annotations

import argparse
import logging
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("resize_image_cache")


def resize_one(args: tuple[Path, Path, int]) -> bool:
    src, dst, max_side = args
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return True
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            scale = max_side / max(im.size)
            if scale < 1:
                im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
            tmp = dst.with_suffix(".tmp")
            im.save(tmp, format="PNG", optimize=False)
            tmp.replace(dst)
        return True
    except OSError as e:
        log.warning("skipped %s (%s)", src.name, e)
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--src", type=Path, default=ROOT / "data" / "scin" / "images")
    p.add_argument("--dst", type=Path, default=ROOT / "data" / "scin" / "images_448")
    p.add_argument("--max-side", type=int, default=448)
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    args.dst.mkdir(parents=True, exist_ok=True)
    jobs = [(f, args.dst / f.name, args.max_side) for f in sorted(args.src.glob("*.png"))]
    with ProcessPoolExecutor(args.workers) as ex:
        ok = sum(ex.map(resize_one, jobs, chunksize=32))
    log.info("cached %d/%d images (longest side <= %d px) -> %s", ok, len(jobs), args.max_side, args.dst)
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
