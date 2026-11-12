import joblib
import pandas as pd

from routeguard import config


def test_metrics_are_sane(workdir):
    m = workdir["metrics"]
    assert 0 < m["base_rate"] < 0.5
    assert m["pr_auc"] > m["base_rate"]  # better than guessing
    assert m["roc_auc"] > 0.55
    assert 0 < m["threshold"] < 1
    assert m["recall_at_threshold"] >= m["recall_at_naive_0.5"]  # cost-based cutoff catches more late orders


def test_bundle_predicts_probabilities_and_reasons(workdir, order):
    model = joblib.load(config.BUNDLE_PATH)
    res = model.predict(pd.DataFrame([order]))[0]
    assert 0.0 <= res["probability"] <= 1.0
    assert res["risk_level"] in {"low", "medium", "high"}
    assert len(res["reasons"]) == 3
    assert all(r["direction"] in {"raises", "lowers"} for r in res["reasons"])


def test_longer_promise_lowers_risk(workdir, order):
    model = joblib.load(config.BUNDLE_PATH)
    tight = {**order, "order_estimated_delivery_date": "2018-03-17T00:00:00"}
    loose = {**order, "order_estimated_delivery_date": "2018-04-20T00:00:00"}
    p_tight, p_loose = (r["probability"] for r in model.predict(pd.DataFrame([tight, loose])))
    assert p_tight >= p_loose


def test_unknown_zip_and_missing_weight_do_not_crash(workdir, order):
    model = joblib.load(config.BUNDLE_PATH)
    odd = {**order, "customer_zip_code_prefix": 99999, "avg_product_weight_g": None, "avg_volume_cm3": None}
    assert 0.0 <= model.predict(pd.DataFrame([odd]))[0]["probability"] <= 1.0
