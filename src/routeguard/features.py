"""Feature engineering used by BOTH training and serving (no copy-paste, no skew)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from routeguard import config


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lng2 - lng1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def add_features(df: pd.DataFrame, geo: pd.DataFrame, peak_months: list[int]) -> pd.DataFrame:
    """Order-level features. `geo` is indexed by zip prefix with lat/lng columns."""
    df = df.copy()
    t = pd.to_datetime(df[config.TIME_COL])
    est = pd.to_datetime(df[config.ESTIMATED_COL])

    df["promised_days"] = (est - t).dt.total_seconds() / 86400
    df["purchase_month"] = t.dt.month
    df["purchase_dow"] = t.dt.dayofweek
    df["purchase_hour"] = t.dt.hour
    df["is_weekend"] = (t.dt.dayofweek >= 5).astype(int)
    df["is_peak_season"] = t.dt.month.isin(peak_months).astype(int)

    c_zip, s_zip = df["customer_zip_code_prefix"], df["seller_zip_code_prefix"]
    df["distance_km"] = haversine_km(
        c_zip.map(geo["lat"]).astype(float), c_zip.map(geo["lng"]).astype(float),
        s_zip.map(geo["lat"]).astype(float), s_zip.map(geo["lng"]).astype(float),
    )  # fmt: skip
    df["km_per_promised_day"] = df["distance_km"] / df["promised_days"].clip(lower=0.5)
    df["is_same_state"] = (df["customer_state"] == df["seller_state"]).astype(int)
    df["freight_ratio"] = df["total_freight"] / df["total_item_price"].clip(lower=1.0)
    df["route"] = df["seller_state"].astype(str) + ">" + df["customer_state"].astype(str)
    return df


# ---- seller history -------------------------------------------------------------------------


def _smooth(late: np.ndarray, n: np.ndarray, prior: float, strength: float) -> np.ndarray:
    return (late + prior * strength) / (n + strength)


def seller_history_time_aware(df: pd.DataFrame, prior: float, strength: float) -> pd.DataFrame:
    """For every order: the seller's late rate using ONLY orders already delivered before
    this order was purchased. That is exactly what we would know in production, so there is
    no leakage from the future."""
    rate = np.full(len(df), prior, dtype=float)
    n_prev = np.zeros(len(df), dtype=float)
    purchase = pd.to_datetime(df[config.TIME_COL]).to_numpy("datetime64[ns]")
    delivered = pd.to_datetime(df[config.DELIVERED_COL]).to_numpy("datetime64[ns]")
    late = df[config.TARGET].to_numpy()

    for _, idx in df.groupby("seller_id").indices.items():
        order = np.argsort(delivered[idx], kind="stable")
        d_sorted = delivered[idx][order]
        cum = np.cumsum(late[idx][order])
        pos = np.searchsorted(d_sorted, purchase[idx], side="left")  # delivered strictly before
        late_before = np.where(pos > 0, cum[np.maximum(pos - 1, 0)], 0)
        rate[idx] = _smooth(late_before, pos.astype(float), prior, strength)
        n_prev[idx] = pos
    return pd.DataFrame({"seller_late_rate": rate, "seller_n_orders": n_prev}, index=df.index)


def seller_snapshot(df: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Latest per-seller totals: seller_id -> (late_count, order_count). Used at serving time."""
    g = df.groupby("seller_id")[config.TARGET].agg(["sum", "count"])
    return {sid: (int(r["sum"]), int(r["count"])) for sid, r in g.iterrows()}


def apply_seller_snapshot(df: pd.DataFrame, snapshot: dict, prior: float, strength: float) -> pd.DataFrame:
    df = df.copy()
    ids = df["seller_id"] if "seller_id" in df.columns else pd.Series(None, index=df.index)
    late = ids.map(lambda s: snapshot.get(s, (0, 0))[0]).astype(float).to_numpy()
    n = ids.map(lambda s: snapshot.get(s, (0, 0))[1]).astype(float).to_numpy()
    df["seller_late_rate"] = _smooth(late, n, prior, strength)
    df["seller_n_orders"] = n
    return df


# ---- final matrix -----------------------------------------------------------------------------


class Featurizer:
    """Turns the engineered frame into the model matrix. Categories are frozen at fit time."""

    def __init__(self, numeric: list[str], categorical: list[str]):
        self.numeric = list(numeric)
        self.categorical = list(categorical)
        self.categories_: dict[str, list[str]] = {}

    def fit(self, df: pd.DataFrame) -> Featurizer:
        for c in self.categorical:
            self.categories_[c] = sorted(df[c].dropna().astype(str).unique())
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        for c in self.numeric:
            X[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        for c in self.categorical:
            s = df[c].astype("object").where(df[c].notna(), None)
            s = s.map(lambda v: None if v is None else str(v))
            X[c] = pd.Categorical(s, categories=self.categories_[c])
        return X
