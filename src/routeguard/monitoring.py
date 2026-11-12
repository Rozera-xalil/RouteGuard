"""Population Stability Index (PSI) drift checks - no extra dependencies."""

from __future__ import annotations

import numpy as np
import pandas as pd

_EPS = 1e-4


def _numeric_bins(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Bin index per value; NaN gets its own last bin."""
    idx = np.searchsorted(edges, values, side="right")
    return np.where(np.isnan(values), len(edges) + 1, idx)


def build_baseline(X: pd.DataFrame, numeric: list[str], categorical: list[str], bins: int = 10) -> dict:
    out: dict = {"numeric": {}, "categorical": {}}
    for c in numeric:
        v = X[c].to_numpy(dtype=float)
        finite = v[~np.isnan(v)]
        edges = (
            np.unique(np.quantile(finite, np.linspace(0, 1, bins + 1)[1:-1])) if len(finite) else np.array([])
        )
        counts = np.bincount(_numeric_bins(v, edges), minlength=len(edges) + 2)
        out["numeric"][c] = {"edges": edges.tolist(), "expected": (counts / counts.sum()).tolist()}
    for c in categorical:
        vc = X[c].astype("object").fillna("__missing__").value_counts(normalize=True)
        out["categorical"][c] = {str(k): float(v) for k, v in vc.items()}
    return out


def psi(expected: np.ndarray, actual: np.ndarray) -> float:
    e = np.clip(np.asarray(expected, dtype=float), _EPS, None)
    a = np.clip(np.asarray(actual, dtype=float), _EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def status_for(value: float, watch: float, alert: float) -> str:
    return "drift" if value >= alert else "watch" if value >= watch else "stable"


def drift_report(
    baseline: dict,
    X: pd.DataFrame,
    exclude: set[str],
    min_rows: int = 30,
    watch: float = 0.10,
    alert: float = 0.25,
) -> dict:
    if len(X) < min_rows:
        return {"status": "insufficient_data", "rows": len(X), "min_rows": min_rows, "features": []}

    feats = []
    for c, b in baseline["numeric"].items():
        if c in exclude:
            continue
        edges = np.asarray(b["edges"], dtype=float)
        counts = np.bincount(_numeric_bins(X[c].to_numpy(dtype=float), edges), minlength=len(b["expected"]))
        feats.append((c, psi(np.asarray(b["expected"]), counts / counts.sum())))
    for c, b in baseline["categorical"].items():
        if c in exclude:
            continue
        cur = X[c].astype("object").fillna("__missing__").value_counts(normalize=True).to_dict()
        keys = sorted(set(b) | set(cur))
        e = np.array([b.get(k, 0.0) for k in keys])
        a = np.array([cur.get(k, 0.0) for k in keys])
        feats.append((c, psi(e, a)))

    rows = [
        {"feature": f, "psi": round(v, 4), "status": status_for(v, watch, alert)}
        for f, v in sorted(feats, key=lambda t: -t[1])
    ]
    worst = rows[0]["psi"] if rows else 0.0
    return {
        "status": status_for(worst, watch, alert),
        "rows": len(X),
        "max_psi": worst,
        "watch_at": watch,
        "alert_at": alert,
        "features": rows,
    }
