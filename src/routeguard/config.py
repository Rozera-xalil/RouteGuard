"""Single source of truth for paths, column names and parameters."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(os.getenv("RG_ROOT", Path(__file__).resolve().parents[2]))

DATA_RAW = Path(os.getenv("RG_DATA_RAW", ROOT / "data" / "raw"))
DATA_PROCESSED = ROOT / "data" / "processed"
ORDERS_CSV = DATA_PROCESSED / "orders.csv"
GEO_CSV = DATA_PROCESSED / "geo.csv"

MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"
BUNDLE_PATH = Path(os.getenv("RG_MODEL_PATH", MODELS_DIR / "routeguard_bundle.joblib"))
DB_PATH = Path(os.getenv("RG_DB_PATH", LOGS_DIR / "predictions.db"))

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}")
MLFLOW_EXPERIMENT = "Olist_Late_Delivery"
REGISTERED_MODEL = "Olist_Late_Delivery_Risk"

TARGET = "late"
TIME_COL = "order_purchase_timestamp"
DELIVERED_COL = "order_delivered_customer_date"
ESTIMATED_COL = "order_estimated_delivery_date"

BR_STATES = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]  # fmt: skip

# Everything below is known at the moment the customer places the order.
NUMERIC_FEATURES = [
    "promised_days",
    "purchase_month",
    "purchase_dow",
    "purchase_hour",
    "is_weekend",
    "is_peak_season",
    "distance_km",
    "km_per_promised_day",
    "is_same_state",
    "total_items",
    "num_sellers",
    "total_item_price",
    "total_freight",
    "freight_ratio",
    "avg_item_price",
    "num_categories",
    "avg_product_weight_g",
    "avg_volume_cm3",
    "max_installments",
    "total_payment_value",
    "seller_late_rate",
    "seller_n_orders",
]
CATEGORICAL_FEATURES = ["customer_state", "seller_state", "route", "payment_types_used"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Seller history grows over time, so it is excluded from drift checks.
DRIFT_EXCLUDE = {"seller_late_rate", "seller_n_orders"}

FEATURE_LABELS = {
    "promised_days": "Promised delivery time (days)",
    "purchase_month": "Month of purchase",
    "purchase_dow": "Day of week",
    "purchase_hour": "Hour of purchase",
    "is_weekend": "Bought on a weekend",
    "is_peak_season": "Peak season (Nov-Mar)",
    "distance_km": "Seller-to-customer distance (km)",
    "km_per_promised_day": "Km to cover per promised day",
    "is_same_state": "Seller and customer in the same state",
    "total_items": "Items in the order",
    "num_sellers": "Number of sellers",
    "total_item_price": "Items price",
    "total_freight": "Freight cost",
    "freight_ratio": "Freight / price ratio",
    "avg_item_price": "Average item price",
    "num_categories": "Product categories",
    "avg_product_weight_g": "Average weight (g)",
    "avg_volume_cm3": "Average package volume (cm3)",
    "max_installments": "Payment installments",
    "total_payment_value": "Total paid",
    "seller_late_rate": "Seller's past late rate",
    "seller_n_orders": "Seller's past orders",
    "customer_state": "Customer state",
    "seller_state": "Seller state",
    "route": "Shipping route",
    "payment_types_used": "Payment type",
}


def load_params(path: Path | None = None) -> dict:
    path = path or ROOT / "params.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
