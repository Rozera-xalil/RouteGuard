import numpy as np
import pandas as pd

from routeguard.monitoring import build_baseline, drift_report, psi


def test_psi_zero_for_identical_and_large_for_shift():
    a = np.array([0.25, 0.25, 0.25, 0.25])
    assert psi(a, a) == 0
    assert psi(a, np.array([0.7, 0.1, 0.1, 0.1])) > 0.25


def test_drift_report_flags_a_shifted_feature_only():
    rng = np.random.default_rng(0)
    base = pd.DataFrame(
        {"x": rng.normal(0, 1, 5000), "y": rng.normal(0, 1, 5000), "c": rng.choice(["a", "b"], 5000)}
    )
    baseline = build_baseline(base, ["x", "y"], ["c"])
    live = pd.DataFrame(
        {"x": rng.normal(2.5, 1, 400), "y": rng.normal(0, 1, 400), "c": rng.choice(["a", "b"], 400)}
    )
    rep = drift_report(baseline, live, exclude=set())
    by = {r["feature"]: r["status"] for r in rep["features"]}
    assert by["x"] == "drift" and by["y"] == "stable" and by["c"] == "stable"
    assert rep["status"] == "drift"


def test_not_enough_rows_is_reported_not_guessed():
    base = pd.DataFrame({"x": range(100)})
    rep = drift_report(build_baseline(base, ["x"], []), base.head(5), exclude=set(), min_rows=30)
    assert rep["status"] == "insufficient_data"
