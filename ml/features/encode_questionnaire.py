"""Encode self-reported SCIN questionnaire fields into features plus a missingness mask.

Each case becomes one row: ``f__*`` feature columns and one ``m__<field>`` mask column per
field (1 = missing / not answered, 0 = present). Nothing is imputed: the features of a missing
field are 0 and must be read together with the mask. An explicit "unknown" answer is a present
answer with its own indicator column. The output is indexed by ``case_id``.

Usage::

    python features/encode_questionnaire.py
    python features/encode_questionnaire.py --data-dir data/scin --out features/questionnaire_features.parquet
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger("encode_questionnaire")
ROOT = Path(__file__).resolve().parents[1]
YES = "YES"


def load_schema(path: Path) -> dict:
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = [f["name"] for f in schema["fields"]]
    if len(set(names)) != len(names):
        raise ValueError("duplicate field names in schema")
    return schema


def load_cases(path: Path, key: str) -> pd.DataFrame:
    # dtype=str keeps the 64-bit case_id exact.
    df = pd.read_csv(path, dtype=str)
    df[key] = df[key].str.strip()
    if df[key].isna().any() or df[key].duplicated().any():
        raise ValueError(f"{key} must be non-null and unique")
    return df.set_index(key)


def _need(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"columns missing in cases CSV: {missing}")


def encode_onehot(df: pd.DataFrame, f: dict, fp: str) -> tuple[pd.DataFrame, pd.Series]:
    s = df[f["column"]].str.strip()
    unknown = f.get("unknown", {})
    allowed = set(f["categories"]) | set(unknown)
    bad = sorted(set(s.dropna()) - allowed)
    if bad:
        raise ValueError(f"{f['name']}: values not in schema: {bad}")
    out = {f"{fp}{f['name']}__{c.lower()}": (s == c).astype("int8") for c in f["categories"]}
    out.update({f"{fp}{f['name']}__{name}": (s == raw).astype("int8") for raw, name in unknown.items()})
    return pd.DataFrame(out, index=df.index), s.isna()


def encode_multihot(df: pd.DataFrame, f: dict, fp: str) -> tuple[pd.DataFrame, pd.Series]:
    cols = {o["name"]: o["column"] for o in f["options"]}
    _need(df, list(cols.values()))
    ticked = pd.DataFrame({n: df[c].eq(YES) for n, c in cols.items()}, index=df.index)
    bad = sorted({v for c in cols.values() for v in df[c].dropna().unique()} - {YES})
    if bad:
        raise ValueError(f"{f['name']}: unexpected cell values {bad}")
    # Blank = option not ticked, so the question counts as unanswered only if nothing is ticked.
    out = ticked.astype("int8").rename(columns=lambda n: f"{fp}{f['name']}__{n}")
    return out, ~ticked.any(axis=1)


def encode_ordinal(df: pd.DataFrame, f: dict, fp: str) -> tuple[pd.DataFrame, pd.Series]:
    s = df[f["column"]].str.strip()
    unknown = f.get("unknown", {})
    rank = {v: i + f["rank_start"] for i, v in enumerate(f["order"])}
    bad = sorted(set(s.dropna()) - set(rank) - set(unknown))
    if bad:
        raise ValueError(f"{f['name']}: values not in schema order: {bad}")
    vals = s.map(rank).fillna(f["missing_fill"]).astype("int8")
    out = {f"{fp}{f['name']}__rank": vals}
    out.update({f"{fp}{f['name']}__{name}": (s == raw).astype("int8") for raw, name in unknown.items()})
    return pd.DataFrame(out, index=df.index), s.isna()


ENCODERS = {"onehot": encode_onehot, "multihot": encode_multihot, "ordinal": encode_ordinal}


def encode(df: pd.DataFrame, schema: dict) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    fp, mp = schema["feature_prefix"], schema["mask_prefix"]
    for f in schema["fields"]:
        if "column" in f:
            _need(df, [f["column"]])
    blocks, masks, groups = [], {}, {}
    for f in schema["fields"]:
        feats, missing = ENCODERS[f["encoding"]](df, f, fp)
        feats = feats.mask(missing, 0).astype("int8")  # missing field -> placeholder 0, flagged by mask
        blocks.append(feats)
        masks[f"{mp}{f['name']}"] = missing.astype("int8")
        groups[f["name"]] = list(feats.columns)
    out = pd.concat(blocks + [pd.DataFrame(masks, index=df.index)], axis=1)
    return out, groups


def validate(out: pd.DataFrame, groups: dict[str, list[str]], schema: dict, n_cases: int) -> None:
    """Raise if any NaN/null remains or the mask is inconsistent with the features."""
    mp = schema["mask_prefix"]
    if len(out) != n_cases or not out.index.is_unique:
        raise AssertionError("row count or case_id uniqueness changed during encoding")
    if out.isna().any().any():
        raise AssertionError("NaN / null values remain; missingness must only be in the mask")
    if not all(np.issubdtype(t, np.number) for t in out.dtypes):
        raise AssertionError("non-numeric column found")
    if not np.isfinite(out.to_numpy(dtype="float64")).all():
        raise AssertionError("non-finite value found")
    for name, cols in groups.items():
        m = out[f"{mp}{name}"]
        if not m.isin([0, 1]).all():
            raise AssertionError(f"mask for {name} is not binary")
        if (out.loc[m == 1, cols] != 0).any().any():
            raise AssertionError(f"{name}: non-zero features where the field is masked missing")
        if (out.loc[m == 0, cols].sum(axis=1) == 0).any() and next(
                f for f in schema["fields"] if f["name"] == name)["encoding"] != "multihot":
            raise AssertionError(f"{name}: answered but all features are zero")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data-dir", type=Path, default=ROOT / "data" / "scin")
    p.add_argument("--schema", type=Path, default=here / "questionnaire_schema.yaml")
    p.add_argument("--out", type=Path, default=here / "questionnaire_features.parquet")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    schema = load_schema(args.schema)
    df = load_cases(args.data_dir / "scin_cases.csv", schema["key"])
    out, groups = encode(df, schema)
    validate(out, groups, schema, len(df))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.out)
    mp = schema["mask_prefix"]
    n_feat = sum(len(c) for c in groups.values())
    log.info("cases=%d features=%d masks=%d -> %s", len(out), n_feat, len(groups), args.out)
    for name in groups:
        log.info("  %-10s missing %5.1f%%", name, 100 * out[f"{mp}{name}"].mean())
    return 0


if __name__ == "__main__":
    sys.exit(main())
