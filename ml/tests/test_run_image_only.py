import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import run_image_only as r  # noqa: E402


def test_sample_weights_give_each_class_the_same_share():
    labels = np.array([0] * 90 + [1] * 9 + [2] * 1)
    w = r.sample_weights(labels, 3)
    shares = [float(w[labels == c].sum()) for c in range(3)]
    assert np.allclose(shares, 1.0)


def test_sampler_numbers_repeated_draws():
    weights = torch.tensor([1.0, 0.0, 0.0], dtype=torch.double)  # always case 0
    s = r.RepeatNumberingSampler(weights, num_samples=4, replacement=True, generator=torch.Generator().manual_seed(0))
    assert list(s) == [0, 3, 6, 9]  # case 0, repeats 0..3 (index = case + n * repeat)


def test_sampler_first_draws_are_plain_indices():
    s = r.RepeatNumberingSampler(torch.ones(50, dtype=torch.double), num_samples=50, replacement=True,
                                 generator=torch.Generator().manual_seed(1))
    idx = list(s)
    assert len(idx) == 50 and len({i % 50 for i in idx}) < 50  # with replacement some cases repeat
    assert sorted({i % 50 for i in idx}) == sorted({i for i in idx if i < 50})


def _flat(seed, worst, f1):
    rows = [{"split": "test", "seed": seed, "missing_pct": 0.0, "scope": "overall", "group": "ALL", "n_cases": 270,
             "metric": "macro_f1", "value": f1, "ci_low": 0, "ci_high": 1},
            {"split": "test", "seed": seed, "missing_pct": 0.0, "scope": "eFST", "group": "I-II", "n_cases": 90,
             "metric": "macro_f1", "value": f1 + 0.1, "ci_low": 0, "ci_high": 1},
            {"split": "test", "seed": seed, "missing_pct": 0.0, "scope": "eFST", "group": f"worst={worst}",
             "n_cases": 25, "metric": "worst_group_macro_f1", "value": f1 - 0.1, "ci_low": 0, "ci_high": 1},
            {"split": "val", "seed": seed, "missing_pct": 0.0, "scope": "overall", "group": "ALL", "n_cases": 270,
             "metric": "macro_f1", "value": 0.99, "ci_low": 0, "ci_high": 1}]
    return pd.DataFrame(rows)


def test_aggregate_seeds_mean_sd_and_tone_groups_kept():
    flat = pd.concat([_flat("0", "V-VI", 0.5), _flat("1", "V-VI", 0.6), _flat("2", "III-IV", 0.7)])
    agg = r.aggregate_seeds(flat).set_index(["scope", "group", "metric"]).drop(columns="missing_pct")
    ov = agg.loc[("overall", "ALL", "macro_f1")]
    assert ov["n_seeds"] == 3 and np.isclose(ov["mean"], 0.6) and np.isclose(ov["sd"], 0.1)  # val rows ignored
    assert np.isclose(agg.loc[("eFST", "I-II", "macro_f1"), "mean"], 0.7)  # tone groups are summarised too
    w = agg.loc[("eFST", "worst", "worst_group_macro_f1")]
    assert w["n_seeds"] == 3 and w["worst_groups"] == "V-VI x2; III-IV x1"
    assert ov["mean_pm_sd"] == "0.600 ± 0.100"


def test_aggregate_seeds_keeps_missing_rates_apart():
    a, b = _flat("0", "V-VI", 0.5), _flat("0", "V-VI", 0.1)
    b["missing_pct"] = 1.0
    agg = r.aggregate_seeds(pd.concat([a, b]))
    ov = agg[(agg.scope == "overall") & (agg.metric == "macro_f1")].set_index("missing_pct")["mean"]
    assert ov.to_dict() == {0.0: 0.5, 1.0: 0.1}


def test_write_seed_runs_keeps_skipped_seeds(tmp_path):
    path = tmp_path / "seed_runs.csv"
    r.write_seed_runs(path, [{"seed": 0, "v": 1}, {"seed": 1, "v": 1}])
    r.write_seed_runs(path, [{"seed": 1, "v": 2}])        # seed 1 re-run, seed 0 skipped
    r.write_seed_runs(path, [{"seed": 5, "v": 3}])        # new seed
    df = pd.read_csv(path)
    assert df["seed"].tolist() == [0, 1, 5] and df["v"].tolist() == [1, 2, 3]
