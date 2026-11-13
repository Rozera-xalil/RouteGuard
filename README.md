![Uploading 575961783-f4b2fe8c-23fb-422f-a69e-96d17420da8c.jpg…]()
<img width="720" height="1612" alt="575961530-ef7bdd31-aaf7-4cea-8cb7-8214666fbcaa" src="https://github.com/user-attachments/assets/abe490d5-94d1-49d8-843a-851dbd0de0f8" />
<img width="1366" height="1193" alt="home" src="https://github.com/user-attachments/assets/0ca4982d-7709-4d93-b2f8-69b917039fd5" />
# RouteGuard: Olist late-delivery risk (v3)

Predicts the chance that an Olist order arrives late **at the moment it is placed**, explains why,
logs every prediction, watches for data drift, and ships with a pink dashboard.

```
raw Olist CSVs -> build_data -> validate (Great Expectations) -> train (Optuna + calibration)
                                                                   |
                       models/routeguard_bundle.joblib  <----------+--> MLflow registry (@champion)
                                  |
              FastAPI  /predict /feedback /monitoring/summary /metrics
                 |            |                        |
          Vue dashboard   SQLite log             Prometheus -> Grafana
```

## What changed from v2

| Area | v2 | v3 |
|---|---|---|
| API probability | took the first ONNX output (the 0/1 label) | real calibrated probability from one bundle |
| Features | zip prefixes one-hot, no promised time | promised days, haversine distance, package size, seller track record (time-aware, no leakage) |
| Training/serving | feature code copied in two places | one `features.py`, one artifact (no skew) |
| Validation | random CV inside train | `TimeSeriesSplit`, PR-AUC, isotonic calibration, cost-based threshold |
| Explanations | none | top 3 reasons per order (LightGBM contributions) |
| Registry | deprecated Stages | MLflow alias `@champion` |
| Monitoring | 0/1 drift counter | PSI per feature, live precision/recall from `/feedback`, Grafana dashboard, alert rules |
| Docker | training libs in the API image | serving-only requirements |
| Tests | 13, no API | 20, including the API, drift and leakage |
| UI | none | Vue 3 dashboard, English / Arabic |

> **ONNX:** v3 serves a single joblib bundle (preprocessing + LightGBM + calibrator + threshold) because
> that removes training/serving skew and keeps calibration. Exporting the raw LightGBM model to ONNX is
> still possible, but then calibration and feature building have to be re-implemented outside it.

## Quick start (no Kaggle needed)

```bash
uv sync --all-groups          # or: pip install -e . plus the groups in pyproject.toml
make demo                     # synthetic data -> validate -> train (a few minutes)
make api                      # http://localhost:8000/docs
cd dashboard && npm install && npm run dev      # http://localhost:5173
```

## With the real Olist data

1. Download the Olist dataset from Kaggle and put these seven CSVs in `data/raw/`:
   `olist_orders_dataset`, `olist_customers_dataset`, `olist_order_items_dataset`,
   `olist_order_payments_dataset`, `olist_products_dataset`, `olist_sellers_dataset`,
   `olist_geolocation_dataset`.
2. `make data validate train` (or `dvc repro` once `dvc init` has been run in your Git repo).
3. Open the MLflow UI: `mlflow ui --backend-store-uri sqlite:///mlflow.db`.

Tune everything in `params.yaml`: split sizes, seller prior, number of Optuna trials, the cost of a
missed late order versus a false alarm (this sets the decision threshold), drift limits.

## Everything in Docker

```bash
cp .env.example .env          # set GRAFANA_PASSWORD
make train                    # the API mounts ./models read-only
docker compose up --build -d
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:8080 |
| API docs | http://localhost:8000/docs |
| Prometheus (+ alerts) | http://localhost:9090 |
| Grafana (dashboard preloaded) | http://localhost:3000 (user `admin`) |

## API

* `POST /predict`: one order -> `probability`, `risk_level`, `predicted_late`, `reasons[]`, `prediction_id`
* `POST /predict/batch`: up to 500 orders
* `POST /feedback`: `{prediction_id, actual_late}`, closes the loop for live accuracy
* `GET /monitoring/summary`: volume, PSI drift per feature, live precision / recall / Brier
* `GET /info`, `/health`, `/features`, `/predictions/recent`, `/metrics`

Risk levels: `high` at or above the cost-optimal threshold, `medium` at half of it or more, else `low`.
Drift needs 30 logged orders before it reports. Seller history features are excluded from drift on purpose
(they grow naturally as time passes).
