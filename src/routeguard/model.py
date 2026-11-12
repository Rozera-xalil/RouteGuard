"""The one artifact the API loads: preprocessing + model + calibration + threshold + baselines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from routeguard import config
from routeguard.features import Featurizer, add_features, apply_seller_snapshot

_OPTIONAL_RAW = [
    "seller_id", "num_sellers", "num_categories", "max_installments",
    "avg_product_weight_g", "avg_volume_cm3", "payment_types_used",
]  # fmt: skip


@dataclass
class RouteGuardModel:
    version: str
    booster: Any  # fitted lightgbm.LGBMClassifier
    calibrator: Any  # fitted IsotonicRegression (raw prob -> calibrated prob)
    featurizer: Featurizer
    geo: pd.DataFrame
    seller_stats: dict
    threshold: float
    params: dict
    baseline: dict
    metrics: dict = field(default_factory=dict)
    importance: list = field(default_factory=list)
    trained_at: str = ""

    # ---- preparation ----------------------------------------------------------------------
    def prepare(self, raw: pd.DataFrame) -> pd.DataFrame:
        f = self.params["features"]
        raw = raw.copy()
        for col in _OPTIONAL_RAW:  # optional inputs: missing means "unknown", not an error
            if col not in raw.columns:
                raw[col] = np.nan
        df = add_features(raw, self.geo, f["peak_months"])
        df = apply_seller_snapshot(df, self.seller_stats, f["seller_prior_rate"], f["seller_prior_strength"])
        return self.featurizer.transform(df)

    # ---- inference ------------------------------------------------------------------------
    def risk_level(self, p: float) -> str:
        return "high" if p >= self.threshold else "medium" if p >= self.threshold / 2 else "low"

    def predict(self, raw: pd.DataFrame, top_k: int = 3) -> list[dict]:
        X = self.prepare(raw)
        raw_p = self.booster.predict_proba(X)[:, 1]
        prob = np.clip(self.calibrator.predict(raw_p), 0.0, 1.0)
        contrib = self.booster.predict(X, pred_contrib=True)[:, :-1]  # drop the bias column

        results = []
        for i in range(len(X)):
            order = np.argsort(-np.abs(contrib[i]))[:top_k]
            reasons = []
            for j in order:
                feat = X.columns[j]
                val = X.iloc[i, j]
                if isinstance(val, float):
                    val = None if np.isnan(val) else round(val, 2)
                reasons.append(
                    {
                        "feature": feat,
                        "label": config.FEATURE_LABELS.get(feat, feat),
                        "value": None if val is None else str(val),
                        "impact": round(float(contrib[i, j]), 3),
                        "direction": "raises" if contrib[i, j] > 0 else "lowers",
                    }
                )
            p = float(prob[i])
            results.append(
                {
                    "probability": round(p, 4),
                    "predicted_late": bool(p >= self.threshold),
                    "risk_level": self.risk_level(p),
                    "threshold": round(self.threshold, 4),
                    "reasons": reasons,
                    "model_version": self.version,
                }
            )
        return results
