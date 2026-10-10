import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import run_e2_dropout as e2  # noqa: E402

CLASSES = ["a", "b", "c"]


def fake_predictions(seeds=(0, 1, 2), n=60, rates=(0.0, 0.5, 1.0)):
    rng = np.random.default_rng(0)
    rows = []
    for s in seeds:
        truth = rng.choice(CLASSES, n)
        efst, emst = rng.integers(1, 7, n), rng.integers(1, 11, n)
        for arm, acc in (("image_only", 0.6), ("nodrop", 0.6), ("fixed", 0.65), ("randdrop", 0.7)):
            for r in ((0.0,) if arm == "image_only" else rates):
                hit = rng.random(n) < acc - (0.1 * r if arm == "nodrop" else 0.0)
                pred = np.where(hit, truth, rng.choice(CLASSES, n))
                rows.append(pd.DataFrame({"case_id": [f"c{s}_{i:03d}" for i in range(n)], "true_label": truth,
                                          "pred_label": pred, "confidence": rng.random(n), "eFST": efst,
                                          "eMST": emst, "seed": s, "missing_pct": r, "arm": arm}))
    return pd.concat(rows, ignore_index=True)


def test_overall_and_groups_build_tables():
    preds, seeds = fake_predictions(), [0, 1, 2]
    arms = ["image_only", "nodrop", "fixed", "randdrop"]
    tab = e2.overall(preds, arms, [0.0, 0.5, 1.0], seeds, CLASSES, n_boot=50, boot_seed=0)
    a = tab[tab["row_type"] == "arm"]
    assert len(a) == 12
    img = a[a["arm"] == "image_only"]["mean"].to_numpy()
    assert np.allclose(img, img[0])                       # photo-only is flat across rates
    pr = tab[(tab["row_type"] == "paired") & (tab["arm"] == "randdrop") & (tab["versus"] == "nodrop")]
    assert len(pr) == 3 and (pr["ci_low"] <= pr["mean"] + 1e-9).all()
    assert set(tab[tab["row_type"] == "drop_r1_vs_r0"]["arm"]) == {"nodrop", "fixed", "randdrop"}
    groups = e2.tone_groups(preds, seeds, CLASSES)
    pg = groups[groups["row_type"] == "paired_group"]
    assert set(pg["arm"]) == {"randdrop", "fixed"} and pg["holm_p"].notna().any()
    text = e2.markdown(tab, groups, {"variant": "concat", "backbone": "b0", "balance": "wl", "seeds": seeds})
    assert "randdrop vs nodrop" in text and "| eFST | V-VI |" in text
