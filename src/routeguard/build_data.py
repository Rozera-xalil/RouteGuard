"""Raw Olist CSVs  ->  one row per delivered order (+ label) and a zip-prefix geo table.

python -m routeguard.build_data
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from routeguard import config

log = logging.getLogger("build_data")

_FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geo": "olist_geolocation_dataset.csv",
}


def load_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [f for f in _FILES.values() if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing in {raw_dir}: {missing}. Download the Olist dataset from Kaggle "
            "or run `python -m routeguard.synthetic` for a toy copy."
        )
    return {k: pd.read_csv(raw_dir / f) for k, f in _FILES.items()}


def build_geo(geo_raw: pd.DataFrame) -> pd.DataFrame:
    """Mean coordinates per 5-digit zip prefix."""
    geo = (
        geo_raw.groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .mean()
        .rename(columns={"geolocation_lat": "lat", "geolocation_lng": "lng"})
    )
    geo.index.name = "zip_prefix"
    return geo


def build_orders(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = raw["orders"].copy()
    for c in [config.TIME_COL, config.DELIVERED_COL, config.ESTIMATED_COL]:
        orders[c] = pd.to_datetime(orders[c], errors="coerce")
    orders = orders[orders["order_status"] == "delivered"]
    orders = orders.dropna(subset=[config.TIME_COL, config.DELIVERED_COL, config.ESTIMATED_COL])
    orders = orders[
        [
            "order_id", "customer_id", config.TIME_COL, config.ESTIMATED_COL, config.DELIVERED_COL,
        ]
    ].merge(
        raw["customers"][["customer_id", "customer_zip_code_prefix", "customer_state"]],
        on="customer_id",
        how="left",
    )  # fmt: skip

    items = (
        raw["items"]
        .merge(raw["sellers"], on="seller_id", how="left")
        .merge(raw["products"], on="product_id", how="left")
        .sort_values(["order_id", "order_item_id"])
    )
    items["volume_cm3"] = items["product_length_cm"] * items["product_height_cm"] * items["product_width_cm"]
    agg = items.groupby("order_id").agg(
        total_items=("order_item_id", "count"),
        num_sellers=("seller_id", "nunique"),
        total_item_price=("price", "sum"),
        total_freight=("freight_value", "sum"),
        avg_item_price=("price", "mean"),
        num_categories=("product_category_name", "nunique"),
        avg_product_weight_g=("product_weight_g", "mean"),
        avg_volume_cm3=("volume_cm3", "mean"),
        seller_id=("seller_id", "first"),
        seller_zip_code_prefix=("seller_zip_code_prefix", "first"),
        seller_state=("seller_state", "first"),
    )

    pay = (
        raw["payments"]
        .groupby("order_id")
        .agg(
            max_installments=("payment_installments", "max"),
            total_payment_value=("payment_value", "sum"),
            payment_types_used=("payment_type", lambda s: "+".join(sorted(s.unique()))),
        )
    )

    df = orders.merge(agg, on="order_id", how="inner").merge(pay, on="order_id", how="left")
    df[config.TARGET] = (df[config.DELIVERED_COL] > df[config.ESTIMATED_COL]).astype(int)
    df = df.sort_values(config.TIME_COL).reset_index(drop=True)
    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    raw = load_raw(config.DATA_RAW)
    geo = build_geo(raw["geo"])
    df = build_orders(raw)
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.ORDERS_CSV, index=False)
    geo.to_csv(config.GEO_CSV)
    log.info("orders: %s rows, late rate %.1f%%", f"{len(df):,}", 100 * np.mean(df[config.TARGET]))
    log.info("geo: %s zip prefixes", f"{len(geo):,}")


if __name__ == "__main__":
    main()
