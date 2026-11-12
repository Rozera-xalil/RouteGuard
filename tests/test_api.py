import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(workdir):
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health_and_info(client):
    h = client.get("/health").json()
    assert h["status"] == "healthy" and h["model_loaded"] is True
    info = client.get("/info").json()
    assert info["threshold"] > 0 and "pr_auc" in info["metrics"] and info["top_drivers"]


def test_predict_returns_probability_not_just_a_label(client, order):
    r = client.post("/predict", json=order)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["probability"] <= 1
    assert body["probability"] not in (0.0, 1.0)  # the old API returned the 0/1 label here
    assert body["prediction_id"] and len(body["reasons"]) == 3


@pytest.mark.parametrize(
    "patch",
    [
        {"seller_state": "XX"},
        {"order_estimated_delivery_date": "2018-03-01T00:00:00"},
        {"total_items": 0},
        {"total_freight": -3},
    ],
)
def test_bad_input_is_rejected_with_422(client, order, patch):
    assert client.post("/predict", json={**order, **patch}).status_code == 422


def test_batch(client, order):
    r = client.post("/predict/batch", json={"orders": [order, {**order, "customer_state": "SP"}]})
    assert r.status_code == 200 and r.json()["total_count"] == 2
    assert client.post("/predict/batch", json={"orders": []}).status_code == 422


def test_feedback_closes_the_loop(client, order):
    pid = client.post("/predict", json=order).json()["prediction_id"]
    assert client.post("/feedback", json={"prediction_id": pid, "actual_late": True}).status_code == 200
    assert client.post("/feedback", json={"prediction_id": "nope", "actual_late": True}).status_code == 404
    live = client.get("/monitoring/summary").json()["live_performance"]
    assert live["n_labeled"] >= 1


def test_drift_needs_enough_traffic_then_reports(client, order):
    for i in range(35):
        client.post("/predict", json={**order, "total_item_price": 100 + i, "avg_item_price": 100 + i})
    drift = client.get("/monitoring/summary").json()["drift"]
    assert drift["status"] in {"stable", "watch", "drift"} and drift["features"]


def test_prometheus_exposes_custom_metrics(client, order):
    client.post("/predict", json=order)
    text = client.get("/metrics").text
    assert "rg_predictions_total" in text and "rg_probability_bucket" in text
