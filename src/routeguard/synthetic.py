"""Tiny Olist-shaped dataset so the whole pipeline can be smoke-tested without Kaggle.

python -m routeguard.synthetic --out data/raw --n 8000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# state -> (lat, lng) rough centres
_STATES = {
    "SP": (-23.5, -46.6), "RJ": (-22.9, -43.2), "MG": (-19.9, -43.9), "RS": (-30.0, -51.2),
    "PR": (-25.4, -49.3), "BA": (-12.9, -38.5), "PE": (-8.0, -34.9), "CE": (-3.7, -38.5),
    "DF": (-15.8, -47.9), "AM": (-3.1, -60.0), "PA": (-1.4, -48.5), "GO": (-16.7, -49.3),
}  # fmt: skip


def _haversine(lat1, lng1, lat2, lng2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def generate(n_orders: int = 8000, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    states = list(_STATES)

    # geography: 8 zip prefixes per state
    geo_rows = []
    for si, st in enumerate(states):
        lat0, lng0 = _STATES[st]
        for k in range(8):
            geo_rows.append(
                (10000 + si * 5000 + k * 137, lat0 + rng.normal(0, 0.15), lng0 + rng.normal(0, 0.15), st)
            )
    geo = pd.DataFrame(
        geo_rows,
        columns=["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_state"],
    )
    geo["geolocation_city"] = "city"
    zips = geo.set_index("geolocation_zip_code_prefix")

    # sellers (some are consistently slow) and customers
    n_sellers = 60
    sel_zip = rng.choice(geo.geolocation_zip_code_prefix.values, n_sellers)
    sellers = pd.DataFrame(
        {
            "seller_id": [f"s{i:03d}" for i in range(n_sellers)],
            "seller_zip_code_prefix": sel_zip,
            "seller_city": "city",
            "seller_state": zips.loc[sel_zip, "geolocation_state"].values,
        }
    )
    slow = rng.random(n_sellers) < 0.2
    seller_delay = np.where(slow, rng.uniform(2.5, 5.0, n_sellers), rng.uniform(0, 1.0, n_sellers))

    n_cust = n_orders
    cust_zip = rng.choice(geo.geolocation_zip_code_prefix.values, n_cust)
    customers = pd.DataFrame(
        {
            "customer_id": [f"c{i:06d}" for i in range(n_cust)],
            "customer_unique_id": [f"u{i:06d}" for i in range(n_cust)],
            "customer_zip_code_prefix": cust_zip,
            "customer_city": "city",
            "customer_state": zips.loc[cust_zip, "geolocation_state"].values,
        }
    )

    products = pd.DataFrame(
        {
            "product_id": [f"p{i:04d}" for i in range(400)],
            "product_category_name": rng.choice(["toys", "beauty", "tech", "home", "sport"], 400),
            "product_weight_g": rng.lognormal(6.5, 0.9, 400).round(),
            "product_length_cm": rng.integers(10, 60, 400),
            "product_height_cm": rng.integers(5, 40, 400),
            "product_width_cm": rng.integers(10, 50, 400),
        }
    )

    start, end = pd.Timestamp("2017-01-01"), pd.Timestamp("2018-08-01")
    span = (end - start).total_seconds()
    purchase = start + pd.to_timedelta(rng.uniform(0, span, n_orders), unit="s")
    purchase = purchase.sort_values()

    oi_rows, pay_rows, order_rows = [], [], []
    for i in range(n_orders):
        oid = f"o{i:06d}"
        s_idx = rng.integers(0, n_sellers)
        n_items = int(rng.choice([1, 1, 1, 2, 3]))
        prods = products.sample(n_items, random_state=int(rng.integers(0, 10**6)))
        price = float(np.round(rng.lognormal(4.2, 0.8), 2))
        freight = float(np.round(8 + rng.gamma(2, 6), 2))
        for j, (_, p) in enumerate(prods.iterrows(), start=1):
            oi_rows.append(
                (
                    oid,
                    j,
                    p.product_id,
                    sellers.seller_id[s_idx],
                    purchase[i] + pd.Timedelta(days=3),
                    price,
                    freight / n_items,
                )
            )
        ptype = rng.choice(["credit_card", "boleto", "voucher"], p=[0.75, 0.2, 0.05])
        pay_rows.append((oid, 1, ptype, int(rng.choice([1, 1, 2, 3, 6, 10])), price * n_items + freight))

        c_zip = int(cust_zip[i])
        dist = float(
            _haversine(
                zips.loc[sel_zip[s_idx], "geolocation_lat"],
                zips.loc[sel_zip[s_idx], "geolocation_lng"],
                zips.loc[c_zip, "geolocation_lat"],
                zips.loc[c_zip, "geolocation_lng"],
            )
        )
        peak = purchase[i].month in (11, 12, 1, 2, 3)
        promised = 9 + dist / 250 + rng.uniform(1, 6)
        actual = (
            4
            + dist / 330
            + seller_delay[s_idx]
            + (3.0 if peak else 0.0)
            + rng.lognormal(1.0, 0.7)
            + n_items * 0.3
        )
        status = "delivered" if rng.random() > 0.04 else "canceled"
        order_rows.append(
            (
                oid, f"c{i:06d}", status, purchase[i], purchase[i] + pd.Timedelta(hours=2),
                purchase[i] + pd.Timedelta(days=2),
                purchase[i] + pd.Timedelta(days=float(actual)) if status == "delivered" else pd.NaT,
                purchase[i] + pd.Timedelta(days=float(promised)),
            )
        )  # fmt: skip

    orders = pd.DataFrame(
        order_rows,
        columns=[
            "order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date",
        ],
    )  # fmt: skip
    items = pd.DataFrame(
        oi_rows,
        columns=[
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ],
    )
    pays = pd.DataFrame(
        pay_rows,
        columns=["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
    )
    return {
        "olist_orders_dataset": orders,
        "olist_customers_dataset": customers,
        "olist_order_items_dataset": items,
        "olist_order_payments_dataset": pays,
        "olist_products_dataset": products,
        "olist_sellers_dataset": sellers,
        "olist_geolocation_dataset": geo,
    }


def write(out: Path, n_orders: int = 8000, seed: int = 7) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, df in generate(n_orders, seed).items():
        df.to_csv(out / f"{name}.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--n", type=int, default=8000)
    args = ap.parse_args()
    write(Path(args.out), args.n)
    print(f"Wrote synthetic Olist-shaped CSVs to {args.out}")
