"""Audit the SCIN (Skin Condition Image Network) metadata.

Loads the SCIN cases and labels CSVs, joins them on ``case_id`` (one row per
case) and writes:

* ``scin_schema.json``      column-level schema (dtype, missingness, values)
* ``scin_audit_report.md``  human-readable audit report
* a ``SCIN`` row upserted into ``data_sources.csv``

Usage::

    python scripts/audit_scin.py --download          # fetch CSVs, then audit
    python scripts/audit_scin.py --data-dir data/scin --out-dir reports

Only the metadata CSVs are needed; images are counted from the image path
columns. Pass ``--images-dir`` to also verify the image files exist locally.

SCIN is released under the SCIN Data Use License
(https://github.com/google-research-datasets/scin/blob/main/LICENSE).
Re-identification of data subjects is prohibited.
"""
from __future__ import annotations

import argparse
import ast
import json
import logging
import sys
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("audit_scin")

GCS_BASE = "https://storage.googleapis.com/dx-scin-public-data/dataset"
CSV_FILES = {
    "cases": "scin_cases.csv",
    "labels": "scin_labels.csv",
    "app_questions": "scin_app_questions.csv",
    "label_questions": "scin_label_questions.csv",
}
LICENCE = "SCIN Data Use License"
LICENCE_URL = "https://github.com/google-research-datasets/scin/blob/main/LICENSE"

KEY = "case_id"
IMAGE_COLS = ["image_1_path", "image_2_path", "image_3_path"]

# Multi-select questions are stored as one column per option holding "YES" or
# blank. A blank cell means "not ticked", so missingness is assessed per family.
CHECKBOX_FAMILIES = [
    "race_ethnicity_",
    "textures_",
    "body_parts_",
    "condition_symptoms_",
    "other_symptoms_",
]
# Answers that are present in the CSV but carry no information.
SENTINELS = {"AGE_UNKNOWN", "OTHER_OR_UNSPECIFIED", "NONE_IDENTIFIED", "UNKNOWN", "PREFER_NOT_TO_ANSWER"}

DERM_FST_COLS = [f"dermatologist_fitzpatrick_skin_type_label_{i}" for i in (1, 2, 3)]
SELF_FST_COL = "fitzpatrick_skin_type"
MST_COLS = {"US": "monk_skin_tone_label_us", "India": "monk_skin_tone_label_india"}
WEIGHTED_LABEL_COL = "weighted_skin_condition_label"

FST_GROUPS = {1: "I-II", 2: "I-II", 3: "III-IV", 4: "III-IV", 5: "V-VI", 6: "V-VI"}


def mst_group(v: float) -> str | float:
    if pd.isna(v):
        return np.nan
    return "1-3" if v <= 3 else "4-6" if v <= 6 else "7-10"


# --------------------------------------------------------------------------- IO
def download(data_dir: Path, overwrite: bool = False) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in CSV_FILES.values():
        target = data_dir / name
        if target.exists() and not overwrite:
            log.info("exists, skipping: %s", target)
            continue
        url = f"{GCS_BASE}/{name}"
        log.info("downloading %s", url)
        urllib.request.urlretrieve(url, target)


def load(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = {k: data_dir / CSV_FILES[k] for k in ("cases", "labels")}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing SCIN files: {missing}. Run with --download.")
    # dtype=str keeps case_id (64-bit signed ints) exact and avoids type guessing.
    cases = pd.read_csv(paths["cases"], dtype=str, keep_default_na=True)
    labels = pd.read_csv(paths["labels"], dtype=str, keep_default_na=True)
    for name, df in (("cases", cases), ("labels", labels)):
        if KEY not in df.columns:
            raise ValueError(f"{name} CSV has no '{KEY}' column")
        df[KEY] = df[KEY].str.strip()
    return cases, labels


def check_keys(cases: pd.DataFrame, labels: pd.DataFrame) -> dict:
    c, l = set(cases[KEY].dropna()), set(labels[KEY].dropna())
    return {
        "cases_rows": len(cases),
        "labels_rows": len(labels),
        "cases_null_ids": int(cases[KEY].isna().sum()),
        "labels_null_ids": int(labels[KEY].isna().sum()),
        "cases_duplicate_ids": int(cases[KEY].duplicated().sum()),
        "labels_duplicate_ids": int(labels[KEY].duplicated().sum()),
        "only_in_cases": len(c - l),
        "only_in_labels": len(l - c),
        "in_both": len(c & l),
    }


def merge(cases: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    cases = cases.dropna(subset=[KEY]).drop_duplicates(KEY)
    labels = labels.dropna(subset=[KEY]).drop_duplicates(KEY)
    overlap = (set(cases.columns) & set(labels.columns)) - {KEY}
    labels = labels.rename(columns={c: f"{c}__labels" for c in overlap})
    df = cases.merge(labels, on=KEY, how="outer", indicator="_merge")
    df = df.set_index(KEY)
    if not df.index.is_unique:
        raise ValueError("case_id is not unique after merge")
    return df


# ----------------------------------------------------------------- derivations
def fst_to_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.extract(r"FST(\d)", expand=False), errors="coerce")


def derive(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns (prefixed with '_') used by the audit."""
    present = [c for c in IMAGE_COLS if c in df.columns]
    df["_n_images"] = df[present].notna().sum(axis=1).astype(int)

    derm = pd.concat([fst_to_int(df[c]) for c in DERM_FST_COLS if c in df.columns], axis=1)
    df["_n_fst_raters"] = derm.notna().sum(axis=1)
    # eFST: median of available dermatologist labels, rounded half up.
    df["_efst"] = np.floor(derm.median(axis=1, skipna=True) + 0.5)
    df["_efst_group"] = df["_efst"].map(FST_GROUPS)
    df["_self_fst"] = fst_to_int(df[SELF_FST_COL]) if SELF_FST_COL in df.columns else np.nan

    for region, col in MST_COLS.items():
        if col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce")
            df[f"_emst_{region.lower()}"] = v
            df[f"_emst_{region.lower()}_group"] = v.map(mst_group)

    if WEIGHTED_LABEL_COL in df.columns:
        parsed = df[WEIGHTED_LABEL_COL].map(_parse_dict)
        df["_n_conditions"] = parsed.map(len)
        df["_top_condition"] = parsed.map(lambda d: max(d, key=d.get) if d else np.nan)
        df["_top_weight"] = parsed.map(lambda d: max(d.values()) if d else np.nan)
    return df


def _parse_dict(v) -> dict:
    if pd.isna(v) or not str(v).strip():
        return {}
    try:
        out = ast.literal_eval(str(v))
        return out if isinstance(out, dict) else {}
    except (ValueError, SyntaxError):
        return {}


# ------------------------------------------------------------------- analyses
def family_of(col: str) -> str | None:
    return next((f.rstrip("_") for f in CHECKBOX_FAMILIES if col.startswith(f)), None)


def missingness(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    n = len(df)
    rows = []
    for c in cols:
        s = df[c]
        na = int(s.isna().sum())
        sent = int(s.isin(SENTINELS).sum())
        rows.append({
            "field": c,
            "family": family_of(c) or "",
            "missing": na,
            "missing_pct": round(100 * na / n, 2) if n else 0.0,
            "sentinel": sent,
            "missing_or_sentinel_pct": round(100 * (na + sent) / n, 2) if n else 0.0,
        })
    return pd.DataFrame(rows)


def family_answer_rates(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for prefix in CHECKBOX_FAMILIES:
        cols = [c for c in df.columns if c.startswith(prefix)]
        if not cols:
            continue
        answered = df[cols].eq("YES").any(axis=1)
        rows.append({
            "family": prefix.rstrip("_"),
            "options": len(cols),
            "answered_cases": int(answered.sum()),
            "unanswered_pct": round(100 * (1 - answered.mean()), 2),
            "mean_options_ticked": round(float(df[cols].eq("YES").sum(axis=1)[answered].mean() or 0), 2),
        })
    return pd.DataFrame(rows)


def distribution(s: pd.Series, sort_index: bool = True) -> pd.DataFrame:
    vc = s.value_counts(dropna=False)
    if sort_index:
        idx = pd.Series(vc.index)
        numeric = pd.to_numeric(idx, errors="coerce").notna().sum() == idx.notna().sum()
        vc = vc.sort_index(key=lambda i: i.map(
            lambda x: (pd.isna(x), float(x) if numeric and not pd.isna(x) else 0.0, str(x))))
    out = vc.rename_axis("value").reset_index(name="cases")
    out["value"] = out["value"].astype(object).where(out["value"].notna(), "missing")
    out["pct"] = (100 * out["cases"] / max(len(s), 1)).round(2)
    return out


def build_schema(df: pd.DataFrame, source_cols: dict[str, list[str]], max_values: int = 15) -> dict:
    fields = []
    for origin, cols in source_cols.items():
        for c in cols:
            if c == KEY:
                s = df.index.to_series()
            else:
                s = df[c] if c in df.columns else df[f"{c}__labels"]
            nunique = int(s.nunique(dropna=True))
            numeric = pd.to_numeric(s, errors="coerce")
            is_numeric = s.notna().sum() > 0 and numeric.notna().sum() == s.notna().sum()
            field = {
                "name": c,
                "source_file": CSV_FILES[origin],
                "inferred_type": "numeric" if is_numeric else "categorical" if nunique <= 50 else "text",
                "family": family_of(c),
                "non_null": int(s.notna().sum()),
                "missing": int(s.isna().sum()),
                "missing_pct": round(100 * s.isna().mean(), 2),
                "n_unique": nunique,
            }
            if c == KEY:
                field["role"] = "primary_key"
                field["inferred_type"] = "identifier"
            if nunique <= max_values:
                field["values"] = {str(k): int(v) for k, v in s.value_counts().items()}
            else:
                field["examples"] = [str(v) for v in s.dropna().unique()[:3]]
            fields.append(field)
    return {"dataset": "SCIN", "primary_key": KEY, "n_cases": len(df), "fields": fields}


# --------------------------------------------------------------------- report
def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_none_\n"
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines) + "\n"


def write_report(path: Path, ctx: dict) -> None:
    k, df = ctx["keys"], ctx["df"]
    n_cases, n_images = len(df), int(df["_n_images"].sum())
    miss = ctx["missing"]
    top_missing = miss[miss.family == ""].sort_values("missing_or_sentinel_pct", ascending=False).head(25)

    parts = [
        "# SCIN metadata audit\n",
        f"Generated {date.today().isoformat()} by `ml/scripts/audit_scin.py`. "
        f"Licence: [{LICENCE}]({LICENCE_URL}) (attribution required when sharing; "
        "re-identification of data subjects prohibited). Informational research use only.\n",
        "## 1. Overview\n",
        md_table(pd.DataFrame([
            ("Cases (unique `case_id`)", n_cases),
            ("Images (non-empty image paths)", n_images),
            ("Mean images per case", round(n_images / max(n_cases, 1), 3)),
            ("Columns in cases CSV", ctx["n_cols"]["cases"]),
            ("Columns in labels CSV", ctx["n_cols"]["labels"]),
        ], columns=["metric", "value"], dtype=object)),
        "## 2. Key integrity (`case_id`)\n",
        md_table(pd.DataFrame(list(k.items()), columns=["check", "value"])),
        "## 3. Images per case\n",
        md_table(distribution(df["_n_images"])),
    ]
    if ctx.get("image_check"):
        parts += ["### Local image files\n", md_table(pd.DataFrame(list(ctx["image_check"].items()), columns=["check", "value"]))]

    parts += [
        "## 4. Missing values\n",
        "Multi-select questions are stored as one `YES`/blank column per option, so a blank cell "
        "there means *not ticked*. Their missingness is reported per question family (4.1). "
        "Single-value fields are reported per column (4.2); *sentinel* counts answers such as "
        f"{', '.join(sorted(SENTINELS))}, which are present but uninformative.\n",
        "### 4.1 Multi-select question families\n",
        md_table(ctx["families"]),
        "### 4.2 Single-value fields (top 25 by missing + sentinel)\n",
        md_table(top_missing.drop(columns="family")),
        "Full per-column figures are in `scin_schema.json`.\n",
        "## 5. Skin tone\n",
        "eFST = median of up to three dermatologist Fitzpatrick labels per case (rounded half up). "
        "eMST = Monk Skin Tone label from the US and India annotator pools.\n",
        "### 5.1 eFST (dermatologist-estimated Fitzpatrick)\n",
        md_table(distribution(df["_efst"].astype("Int64"))),
        md_table(distribution(df["_efst_group"])),
        "Number of dermatologist FST labels per case:\n",
        md_table(distribution(df["_n_fst_raters"])),
        "### 5.2 Self-reported Fitzpatrick\n",
        md_table(distribution(df[SELF_FST_COL])),
    ]
    for region in MST_COLS:
        col = f"_emst_{region.lower()}"
        if col in df.columns:
            parts += [f"### 5.{3 if region == 'US' else 4} eMST ({region} annotators)\n",
                      md_table(distribution(df[col].astype("Int64"))),
                      md_table(distribution(df[f"{col}_group"]))]
    if "_efst_group" in df.columns and "_emst_us_group" in df.columns:
        ct = pd.crosstab(df["_efst_group"].fillna("missing"), df["_emst_us_group"].fillna("missing"))
        parts += ["### 5.5 eFST group x eMST (US) group\n", md_table(ct.reset_index().rename(columns={"_efst_group": "eFST \\ eMST"}))]

    if "_top_condition" in df.columns:
        labelled = df["_top_condition"].notna()
        parts += [
            "## 6. Dermatologist condition labels\n",
            f"Cases with at least one weighted condition label: {int(labelled.sum())} "
            f"({100 * labelled.mean():.1f}%). The table lists the 25 most frequent top-weighted "
            "conditions; these are dermatologist differentials, not confirmed outcomes.\n",
            md_table(distribution(df["_top_condition"].dropna(), sort_index=False).head(25)),
            "Image-quality gradability (first dermatologist):\n",
            md_table(distribution(df.get("dermatologist_gradable_for_skin_condition_1", pd.Series(dtype=str)))),
        ]
    parts += [
        "## 7. Notes for downstream use\n",
        "- Split train/validation/test by `case_id`, never by image, so photos of one case stay together.\n"
        "- Skin-tone groups V-VI (eFST) and 7-10 (eMST) are small; report confidence intervals for them.\n"
        "- eMST labels from the US and India annotator pools differ; choose one pool and report it.\n"
        "- Condition labels are retrospective dermatologist differentials from images and self-reported data.\n",
    ]
    path.write_text("\n".join(parts), encoding="utf-8")


def upsert_source(path: Path, row: dict) -> None:
    cols = ["source", "licence", "case_count", "image_count", "notes"]
    df = pd.read_csv(path, dtype=str) if path.exists() else pd.DataFrame(columns=cols)
    df = df[df["source"] != row["source"]]
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)[cols]
    df.to_csv(path, index=False)


def check_images(df: pd.DataFrame, images_dir: Path) -> dict:
    paths = pd.Series(df[[c for c in IMAGE_COLS if c in df.columns]].values.ravel()).dropna()
    exists = paths.map(lambda p: (images_dir / Path(p).name).exists())
    return {"referenced": len(paths), "found": int(exists.sum()), "missing": int((~exists).sum())}


# ----------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--data-dir", type=Path, default=root / "data" / "scin")
    p.add_argument("--out-dir", type=Path, default=root / "reports")
    p.add_argument("--sources-csv", type=Path, default=root / "data_sources.csv")
    p.add_argument("--images-dir", type=Path, default=None, help="optional: verify image files exist")
    p.add_argument("--download", action="store_true", help="download the SCIN CSVs from GCS first")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.download:
        download(args.data_dir)
    cases, labels = load(args.data_dir)
    keys = check_keys(cases, labels)
    if keys["cases_duplicate_ids"] or keys["labels_duplicate_ids"]:
        log.warning("duplicate case_id values found; keeping the first occurrence")

    df = derive(merge(cases, labels))
    data_cols = [c for c in df.columns if not c.startswith("_")]
    ctx = {
        "df": df,
        "keys": keys,
        "n_cols": {"cases": cases.shape[1], "labels": labels.shape[1]},
        "missing": missingness(df, data_cols),
        "families": family_answer_rates(df),
    }
    if args.images_dir:
        ctx["image_check"] = check_images(df, args.images_dir)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    schema = build_schema(df, {
        "cases": list(cases.columns),
        "labels": [c for c in labels.columns if c != KEY],
    })
    schema["key_integrity"] = keys
    (args.out_dir / "scin_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    write_report(args.out_dir / "scin_audit_report.md", ctx)

    n_images = int(df["_n_images"].sum())
    upsert_source(args.sources_csv, {
        "source": "SCIN",
        "licence": f"{LICENCE} ({LICENCE_URL})",
        "case_count": len(df),
        "image_count": n_images,
        "notes": f"release {df['release'].dropna().iloc[0] if 'release' in df and df['release'].notna().any() else '?'}; "
                 f"gs://dx-scin-public-data; audited {date.today().isoformat()}; split by case_id",
    })
    log.info("cases=%d images=%d -> %s", len(df), n_images, args.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
