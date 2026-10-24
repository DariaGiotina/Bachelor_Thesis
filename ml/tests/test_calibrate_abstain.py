import numpy as np
import pandas as pd

import abstain as ab
import calibrate as cal


def test_temperature_recovers_overconfidence():
    rng = np.random.default_rng(0)
    n, k = 4000, 4
    true_logits = rng.normal(0, 1.5, (n, k))
    y = np.array([rng.choice(k, p=p) for p in cal.softmax(true_logits)])
    overconfident = cal.softmax(true_logits * 3)  # same ranking, three times too sharp
    t = cal.fit_temperature(cal.to_logits(overconfident), y)
    assert 2.5 < t < 3.5
    assert cal.nll(cal.to_logits(overconfident), y, t) < cal.nll(cal.to_logits(overconfident), y)


def test_temperature_keeps_the_predicted_class():
    p = cal.softmax(np.random.default_rng(1).normal(size=(50, 4)))
    assert (cal.apply_temperature(p, 2.0).argmax(1) == p.argmax(1)).all()


def test_tau_gives_target_coverage():
    conf = np.linspace(0, 1, 1001)
    tau = ab.choose_tau(conf, 0.8)
    assert abs((conf >= tau).mean() - 0.8) < 0.002


def test_selective_metrics():
    correct = np.array([1, 1, 0, 0, 1], bool)
    answered = np.array([1, 1, 1, 0, 0], bool)
    s = ab.selective(correct, answered)
    assert s["coverage"] == 0.6 and np.isclose(s["selective_accuracy"], 2 / 3)
    assert s["abstention_precision"] == 0.5 and s["accuracy"] == 0.6


def test_group_report_point_values_and_paired_difference():
    df = pd.DataFrame({"seed": [0] * 8, "case_id": list("abcdefgh"),
                       "correct": [1, 1, 1, 1, 0, 0, 1, 1], "answered": [1, 1, 1, 1, 0, 0, 1, 0],
                       "g": ["x"] * 4 + ["y"] * 4})
    rep = ab.group_report(df, "g", ["x", "y"], [("y", "x")], n_boot=50)
    v = rep.set_index(["group", "metric"])["value"]
    assert v[("x", "abstention_rate")] == 0.0 and v[("y", "abstention_rate")] == 0.75
    assert v[("y - x", "abstention_rate")] == 0.75


def test_cluster_bootstrap_keeps_repeated_rows_together():
    ids = np.array(["a", "a", "b", "b", "c", "c"])
    for draw in ab._cluster_index(ids, 20, np.random.default_rng(0)):
        assert len(draw) == 6
        counts = pd.Series(ids[draw]).value_counts()
        assert (counts % 2 == 0).all()  # every case enters with both of its rows


def test_gradcam_helpers():
    import torch
    import run_gradcam as rg

    t = torch.arange(2 * 5 * 3, dtype=torch.float).reshape(2, 5, 3)  # 1 prefix token + 2 x 2 patches
    out = rg.vit_reshape(2, 1)(t)
    assert out.shape == (2, 3, 2, 2) and torch.equal(out[0, :, 0, 0], t[0, 1])
    a = np.arange(64, dtype=float).reshape(8, 8)
    assert np.isclose(rg.rho(a, a, step=1), 1.0) and np.isnan(rg.rho(a, np.ones((8, 8)), step=1))
    lin = torch.nn.Linear(4, 2)
    m = torch.nn.Sequential(torch.nn.Linear(4, 4), lin)
    r = rg.randomised(m, [lin], 0)
    assert torch.equal(r[0].weight, m[0].weight) and not torch.equal(r[1].weight, m[1].weight)
