"""Task 4.5: registry of every reported number, and a check that each one still follows from the runs.

Every cell of the result tables of the thesis (``reports/assets/tables/``, built by
``make_report_assets.py``) and every number of the exported model's check becomes one row of
``results/results_registry.csv`` with: where it is reported, its value, the stored results file it
comes from, the command that produces that file, the split seeds, the configuration file and the
run folder with the per-seed checkpoints (git-ignored, on the training PC).

``--check`` rebuilds every table from the stored results and stops if a committed table differs, so a
table can never drift from the results it claims to show.

Usage::

    python results_registry.py            # check, then write results/results_registry.csv
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import make_report_assets as mra  # noqa: E402
from data_loading import ROOT  # noqa: E402
from run_e1 import arm_spec  # noqa: E402

log = logging.getLogger("results_registry")
SEEDS = "0-9"
ASSETS = ROOT / "reports" / "assets" / "tables"
EXPORT_JSON = ROOT / "export" / "skin_concern_dinov2.json"
OUT = ROOT / "results" / "results_registry.csv"

# table -> (command that writes its results file, thesis section and table)
COMMANDS = {
    "e1_questionnaire": ("python run_e1.py --seeds 0 1 2 3 4 5 6 7 8 9 --arms image_only questionnaire_only "
                         "fusion_concat fusion_gated fusion_film fusion_concat_nodrop ensemble_image_q", "8.1, Table 8.1"),
    "e2_missing_answers": ("python run_e2_dropout.py --seeds 0 1 2 3 4 5 6 7 8 9", "8.3, Table 8.3, Figure 8.1"),
    "e3_by_tone": ("python analyze_fairness.py", "8.8, Table 8.11"),
    "e4_calibration": ("python calibrate.py --export image_only fusion_film; python run_e4.py", "8.6, Table 8.6"),
    "e4_ood_detector": ("python ood_detect.py", "8.6, Table 8.9"),
    "e5_encoders": ("python run_e1.py --seeds 0 1 2 3 4 5 6 7 8 9 --arms image_only probe_effb0 probe_vit_in21k "
                    "probe_dinov2 probe_panderm_base probe_panderm_large probe_dermlip --out-dir results/e5 --name e5", "8.5, Table 8.5"),
    "e7_extra_data": ("python run_fitz_pooling.py --arms fitz_pooled fitz_pretrain --seeds 0 1 2 3 4 5 6 7 8 9", "8.4, Table 8.4"),
    "stats_contrasts": ("python stats_tests.py", "8.8 (statistics)"),
}
ARM_OF = {v: k for k, v in mra.NAMES.items()}
E2_ARMS = {"nodrop": "fusion_concat_nodrop", "fixed": "fusion_concat", "randdrop": "fusion_concat_randdrop"}


def run_dir(table: str, row: str) -> Path | None:
    """Folder of the per-seed runs behind one table row (None for derived rows, e.g. contrasts)."""
    if table == "stats_contrasts":
        return None
    if table == "e4_ood_detector":
        return arm_spec("probe_dinov2", "efficientnet_b0", "weighted_loss")["dir"]
    arm = ARM_OF.get(row, row)
    arm = E2_ARMS.get(arm, arm)
    if arm in ("fitz_pooled", "fitz_pretrain"):
        return ROOT / "runs" / "e7_fitzpatrick" / f"efficientnet_b0_{arm}"
    return arm_spec(arm, "efficientnet_b0", "weighted_loss")["dir"]


def checkpoints(d: Path | None) -> str:
    """Per-seed checkpoint pattern inside a run folder, as stored on the training PC."""
    if d is None or not d.exists():
        return ""
    rel = d.relative_to(ROOT).as_posix()
    ck = sorted((d / "seed_checkpoints").glob("*seed0.pt")) if (d / "seed_checkpoints").is_dir() else []
    if ck:
        return f"{rel}/seed_checkpoints/{ck[0].name.replace('seed0', 'seed{k}')}"
    if (d / "probe_seed0.pt").exists():
        return f"{rel}/probe_seed{{k}}.pt"
    if any(d.glob("seed0/*.pt")):
        return f"{rel}/seed{{k}}/{next(d.glob('seed0/*.pt')).name}"
    return f"{rel}/seed{{k}}/predictions.csv (no checkpoint: derived from other arms)"


def config(d: Path | None) -> str:
    if d is not None and (d / "config_used.yaml").exists():
        return (d / "config_used.yaml").relative_to(ROOT).as_posix()
    return "configs/base.yaml"


def check_tables() -> list[str]:
    """Rebuild each table from the stored results; names of tables that differ from the committed CSV."""
    bad = []
    for name, (fn, _, _) in mra.TABLES.items():
        fresh = fn().astype(str).reset_index(drop=True)
        committed = pd.read_csv(ASSETS / f"{name}.csv", dtype=str, keep_default_na=False)
        fresh.columns = committed.columns if len(fresh.columns) == len(committed.columns) else fresh.columns
        if fresh.shape != committed.shape or not (fresh.to_numpy() == committed.to_numpy()).all():
            bad.append(name)
    return bad


def registry() -> pd.DataFrame:
    rows = []
    for name, (_, src, title) in mra.TABLES.items():
        t = pd.read_csv(ASSETS / f"{name}.csv", dtype=str, keep_default_na=False)
        key = t.columns[0] if name != "stats_contrasts" else "contrast"
        cmd, where = COMMANDS[name]
        for _, r in t.iterrows():
            d = run_dir(name, r[t.columns[0]])
            for col in t.columns:
                if col in (t.columns[0], key) or (name == "stats_contrasts" and col in ("family", "metric")):
                    continue
                label = r[key] if name != "stats_contrasts" else f"{r['contrast']} ({r['metric']})"
                rows.append({"id": f"{name}|{label}|{col}", "table": f"reports/assets/tables/{name}.csv",
                             "reported_in": where, "quantity": f"{title}: {label}, {col}", "value": r[col],
                             "results_file": src, "command": cmd, "seeds": SEEDS, "config": config(d),
                             "checkpoints": checkpoints(d)})
    if EXPORT_JSON.exists():
        meta = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
        flat = {"temperature": meta["temperature"], "tau": meta["tau"], "knn_threshold": meta["knn"]["threshold"],
                **{f"test_{k}": v for k, v in meta["check"]["test_exported"].items()},
                **{f"test_with_knn_{k}": v for k, v in meta["check"]["test_exported_with_knn_filter"].items()},
                "onnx_vs_stored_e5_class_agreement": meta["check"]["onnx_vs_stored_e5_class_agreement"]}
        seed = meta["probe"]["seed"]
        for k, v in flat.items():
            rows.append({"id": f"export|{k}", "table": "results/export/export_check.md", "reported_in": "6.1, Table 6.1",
                         "quantity": f"exported app model: {k}", "value": f"{v:.4f}",
                         "results_file": "export/skin_concern_dinov2.json", "command": "python export_model.py",
                         "seeds": str(seed), "config": "configs/base.yaml",
                         "checkpoints": f"runs/foundation_probe/timm_vit_base_patch14_dinov2.lvd142m/probe_seed{seed}.pt"})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--no-check", action="store_true", help="skip rebuilding the tables")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.no_check:
        bad = check_tables()
        if bad:
            log.error("tables differ from the stored results: %s (run make_report_assets.py)", ", ".join(bad))
            return 1
        log.info("all %d tables rebuild identically from the stored results", len(mra.TABLES))
    reg = registry()
    reg.to_csv(args.out, index=False)
    log.info("%d reported numbers -> %s", len(reg), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
