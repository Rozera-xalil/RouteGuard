import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from app.schemas import (
    BatchRequest,
    BatchResponse,
    FeedbackRequest,
    HealthResponse,
    OrderInput,
    PredictionResult,
)
from app.store import PredictionStore
from routeguard import config
from routeguard.model import RouteGuardModel  # noqa: F401  (needed to unpickle the bundle)
from routeguard.monitoring import drift_report

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s | %(levelname)-7s | %(message)s"
)
log = logging.getLogger("routeguard.api")

PREDICTIONS = Counter("rg_predictions_total", "Predictions by risk level", ["risk_level"])
PROBABILITY = Histogram(
    "rg_probability", "Calibrated late probability",
    buckets=(0.02, 0.05, 0.08, 0.12, 0.17, 0.25, 0.35, 0.5, 0.75, 1.0),
)  # fmt: skip
FEEDBACK = Counter("rg_feedback_total", "Outcomes reported back", ["actual_late"])
PSI_FEATURE = Gauge("rg_feature_psi", "PSI of a feature vs the training baseline", ["feature"])
PSI_MAX = Gauge("rg_feature_psi_max", "Largest feature PSI (0 when not enough data)")
DRIFT_INTERVAL = int(os.getenv("RG_DRIFT_INTERVAL", "60"))

state: dict = {"model": None, "store": None}


def _drift() -> dict:
    model: RouteGuardModel | None = state["model"]
    store: PredictionStore = state["store"]
    if model is None:
        return {"status": "no_model", "features": []}
    d = model.params["drift"]
    payloads = store.recent_payloads(1000)
    if not payloads:
        return {"status": "insufficient_data", "rows": 0, "min_rows": d["min_rows"], "features": []}
    X = model.prepare(pd.DataFrame(payloads))
    return drift_report(
        model.baseline, X, config.DRIFT_EXCLUDE, d["min_rows"], d["watch_psi"], d["alert_psi"]
    )


def _publish_drift() -> dict:
    rep = _drift()
    PSI_MAX.set(rep.get("max_psi", 0.0))
    for f in rep["features"]:
        PSI_FEATURE.labels(feature=f["feature"]).set(f["psi"])
    return rep


async def _drift_loop():
    while True:
        try:
            await asyncio.to_thread(_publish_drift)
        except Exception:
            log.exception("drift refresh failed")
        await asyncio.sleep(DRIFT_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["store"] = PredictionStore(config.DB_PATH)
    try:
        state["model"] = joblib.load(config.BUNDLE_PATH)
        log.info("Loaded model %s from %s", state["model"].version, config.BUNDLE_PATH)
    except Exception:
        state["model"] = None
        log.exception("Could not load model bundle at %s", config.BUNDLE_PATH)
    task = asyncio.create_task(_drift_loop())
    yield
    task.cancel()
    state.clear()


app = FastAPI(
    title="RouteGuard - Olist late-delivery risk",
    description="Predicts the chance an order arrives late, explains why, and watches for drift.",
    version="3.0.0",
    lifespan=lifespan,
)
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app, include_in_schema=False)


def _model() -> RouteGuardModel:
    if state.get("model") is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model is not loaded")
    return state["model"]


def _run(orders: list[OrderInput]) -> list[PredictionResult]:
    model = _model()
    payloads = [o.model_dump(mode="json") for o in orders]
    results = model.predict(pd.DataFrame(payloads))
    out = []
    for o, payload, res in zip(orders, payloads, results, strict=True):
        pid = uuid.uuid4().hex[:12]
        state["store"].add(pid, o.order_id, payload, res)
        PREDICTIONS.labels(risk_level=res["risk_level"]).inc()
        PROBABILITY.observe(res["probability"])
        out.append(PredictionResult(prediction_id=pid, order_id=o.order_id, **res))
    return out


# ---- observability ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["Observability"])
def health():
    m = state.get("model")
    return HealthResponse(
        status="healthy" if m else "unhealthy",
        model_loaded=m is not None,
        model_version=m.version if m else None,
    )


@app.get("/info", tags=["Observability"])
def info():
    m = _model()
    return {
        "model_version": m.version,
        "trained_at": m.trained_at,
        "threshold": m.threshold,
        "metrics": m.metrics,
        "top_drivers": m.importance,
        "decision_costs": m.params["decision"],
    }


@app.get("/features", tags=["Observability"])
def features():
    m = _model()
    return {"numeric": m.featurizer.numeric, "categorical": m.featurizer.categorical}


@app.get("/monitoring/summary", tags=["Observability"])
def monitoring_summary():
    store: PredictionStore = state["store"]
    return {
        "volume": store.volume(),
        "drift": _publish_drift(),
        "live_performance": store.live_performance(),
    }


@app.get("/predictions/recent", tags=["Observability"])
def recent(limit: int = 10):
    return state["store"].recent(max(1, min(limit, 100)))


# ---- inference -------------------------------------------------------------------------------
@app.post("/predict", response_model=PredictionResult, tags=["Inference"])
def predict_one(order: OrderInput):
    return _run([order])[0]


@app.post("/predict/batch", response_model=BatchResponse, tags=["Inference"])
def predict_batch(batch: BatchRequest):
    preds = _run(batch.orders)
    return BatchResponse(predictions=preds, total_count=len(preds), model_version=_model().version)


@app.post("/feedback", tags=["Inference"])
def feedback(fb: FeedbackRequest):
    """Tell us how the order really ended. This is how live accuracy gets measured."""
    if not state["store"].set_actual(fb.prediction_id, fb.actual_late):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown prediction_id")
    FEEDBACK.labels(actual_late=str(fb.actual_late).lower()).inc()
    return {"status": "recorded"}
