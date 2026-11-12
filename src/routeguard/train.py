"""Train, tune, calibrate, pick a cost-based threshold, evaluate on the newest orders, save.

python -m routeguard.train                # full run (needs data/processed from build_data)
python -m routeguard.train --n-trials 5   # quicker
python -m routeguard.train --no-mlflow
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from routeguard import config
from routeguard.features import (
    Featurizer,
    add_features,
    seller_history_time_aware,
    seller_snapshot,
)
from routeguard.model import RouteGuardModel
from routeguard.monitoring import build_baseline

log = logging.getLogger("train")


# ---- helpers ----------------------------------------------------------------------------------
def split_by_time(df: pd.DataFrame, train: float, val: float):
    """Oldest -> train, middle -> validation (calibration + threshold), newest -> test."""
    df = df.sort_values(config.TIME_COL).reset_index(drop=True)
    a = int(len(df) * train)
    b = a + int(len(df) * val)
    return df.iloc[:a], df.iloc[a:b], df.iloc[b:]


def pick_threshold(y: np.ndarray, p: np.ndarray, cost_fn: float, cost_fp: float) -> tuple[float, float]:
    """Threshold on calibrated probabilities that minimises total business cost."""
    candidates = np.unique(np.quantile(p, np.linspace(0.30, 0.999, 300)))
    candidates = candidates[candidates > 0]
    best_t, best_c = 0.5, np.inf
    for t in candidates:
        pred = p >= t
        cost = cost_fn * np.sum((~pred) & (y == 1)) + cost_fp * np.sum(pred & (y == 0))
        if cost < best_c:
            best_t, best_c = float(t), float(cost)
    return best_t, best_c


def lift_at(y: np.ndarray, p: np.ndarray, frac: float = 0.10) -> float:
    k = max(1, int(len(y) * frac))
    top = np.argsort(-p)[:k]
    return float((y[top].sum() / max(y.sum(), 1)) / frac)


def evaluate(y, raw_p, cal_p, thr) -> dict:
    pred = cal_p >= thr
    tp = int(np.sum(pred & (y == 1)))
    naive = raw_p >= 0.5
    return {
        "n_test": int(len(y)),
        "base_rate": float(y.mean()),
        "pr_auc": float(average_precision_score(y, cal_p)),
        "roc_auc": float(roc_auc_score(y, cal_p)),
        "brier_raw": float(brier_score_loss(y, raw_p)),
        "brier_calibrated": float(brier_score_loss(y, cal_p)),
        "threshold": float(thr),
        "precision_at_threshold": float(tp / max(pred.sum(), 1)),
        "recall_at_threshold": float(tp / max(y.sum(), 1)),
        "flagged_share": float(pred.mean()),
        "lift_at_10pct": lift_at(y, cal_p),
        "recall_at_naive_0.5": float(np.sum(naive & (y == 1)) / max(y.sum(), 1)),
    }


def tune(X: pd.DataFrame, y: pd.Series, n_trials: int, cv_splits: int, seed: int) -> dict:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 150, 600),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 96),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 120),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        scores = []
        # time-ordered folds: never train on the future of the validation fold
        for tr, va in TimeSeriesSplit(n_splits=cv_splits).split(X):
            m = lgb.LGBMClassifier(**_fixed(seed), **params).fit(X.iloc[tr], y.iloc[tr])
            scores.append(average_precision_score(y.iloc[va], m.predict_proba(X.iloc[va])[:, 1]))
        return float(np.mean(scores))

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    log.info("best CV PR-AUC %.4f", study.best_value)
    return study.best_params


def _fixed(seed: int) -> dict:
    return {
        "subsample_freq": 1,
        "cat_smooth": 20,
        "cat_l2": 10,
        "min_data_per_group": 50,
        "random_state": seed,
        "n_jobs": -1,
        "verbose": -1,
    }


def save_figure(y, raw_p, cal_p, importance, path) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.calibration import calibration_curve
        from sklearn.metrics import precision_recall_curve
    except ImportError:
        return
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    pr, rc, _ = precision_recall_curve(y, cal_p)
    ax[0].plot(rc, pr, color="#D6366F", lw=2)
    ax[0].axhline(y.mean(), ls="--", color="#999", label="base rate")
    ax[0].set(title="Precision-Recall (test)", xlabel="recall", ylabel="precision")
    ax[0].legend()
    for name, p, c in [("raw", raw_p, "#bbb"), ("calibrated", cal_p, "#D6366F")]:
        fp, mp = calibration_curve(y, p, n_bins=10, strategy="quantile")
        ax[1].plot(mp, fp, marker="o", color=c, label=name)
    ax[1].plot([0, 1], [0, 1], ls="--", color="#999")
    ax[1].set(title="Calibration (test)", xlabel="predicted", ylabel="observed")
    ax[1].legend()
    top = importance[:10][::-1]
    ax[2].barh([t["label"] for t in top], [t["share"] for t in top], color="#F48FB1")
    ax[2].set(title="What drives the risk (gain share)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---- main -------------------------------------------------------------------------------------
def run(n_trials: int | None = None, use_mlflow: bool = True) -> dict:
    params = config.load_params()
    seed = params["train"]["seed"]
    n_trials = n_trials if n_trials is not None else params["train"]["n_trials"]

    orders = pd.read_csv(
        config.ORDERS_CSV, parse_dates=[config.TIME_COL, config.ESTIMATED_COL, config.DELIVERED_COL]
    )
    geo = pd.read_csv(config.GEO_CSV, index_col="zip_prefix")
    fcfg = params["features"]

    df = add_features(orders, geo, fcfg["peak_months"])
    hist = seller_history_time_aware(df, fcfg["seller_prior_rate"], fcfg["seller_prior_strength"])
    df = pd.concat([df, hist], axis=1)

    train, val, test = split_by_time(df, params["split"]["train"], params["split"]["val"])
    log.info("train %s | val %s | test %s", len(train), len(val), len(test))

    fz = Featurizer(config.NUMERIC_FEATURES, config.CATEGORICAL_FEATURES).fit(train)
    X_tr, X_va, X_te = fz.transform(train), fz.transform(val), fz.transform(test)
    y_tr, y_va, y_te = (d[config.TARGET].to_numpy() for d in (train, val, test))

    best = tune(X_tr, pd.Series(y_tr), n_trials, params["train"]["cv_splits"], seed)
    clf = lgb.LGBMClassifier(**_fixed(seed), **best).fit(X_tr, y_tr)

    raw_va = clf.predict_proba(X_va)[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw_va, y_va)
    cal_va = calibrator.predict(raw_va)
    thr, val_cost = pick_threshold(
        y_va, cal_va, params["decision"]["cost_missed_late"], params["decision"]["cost_false_alarm"]
    )

    raw_te = clf.predict_proba(X_te)[:, 1]
    cal_te = calibrator.predict(raw_te)
    metrics = evaluate(y_te, raw_te, cal_te, thr)
    metrics["val_cost"] = val_cost
    log.info("test: %s", json.dumps({k: round(v, 4) for k, v in metrics.items()}))

    gain = clf.booster_.feature_importance("gain")
    share = gain / max(gain.sum(), 1e-9)
    importance = sorted(
        (
            {"feature": f, "label": config.FEATURE_LABELS.get(f, f), "share": round(float(s), 4)}
            for f, s in zip(X_tr.columns, share, strict=True)
        ),
        key=lambda d: -d["share"],
    )

    # The shipped model sees all labelled history for seller stats (what production would know).
    now = datetime.now(UTC)
    model = RouteGuardModel(
        version=f"v3-{now:%Y%m%d%H%M}",
        booster=clf,
        calibrator=calibrator,
        featurizer=fz,
        geo=geo,
        seller_stats=seller_snapshot(df),
        threshold=thr,
        params=params,
        baseline={},
        metrics=metrics,
        importance=importance[:12],
        trained_at=now.isoformat(timespec="seconds"),
    )
    sample = train.sample(min(20000, len(train)), random_state=seed)
    model.baseline = build_baseline(
        model.prepare(sample), config.NUMERIC_FEATURES, config.CATEGORICAL_FEATURES
    )

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, config.BUNDLE_PATH)
    (config.REPORTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    fig_path = config.REPORTS_DIR / "evaluation.png"
    save_figure(y_te, raw_te, cal_te, importance, fig_path)
    log.info("saved %s", config.BUNDLE_PATH)

    if use_mlflow:
        log_to_mlflow(model, best, metrics, fig_path)
    return metrics


def log_to_mlflow(model: RouteGuardModel, best_params: dict, metrics: dict, fig_path) -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    from routeguard.registry import RiskPyfunc

    mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(config.MLFLOW_EXPERIMENT)
    with mlflow.start_run(run_name=model.version):
        mlflow.log_params(best_params)
        mlflow.log_params({f"decision_{k}": v for k, v in model.params["decision"].items()})
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, int | float)})
        mlflow.set_tag("model_version", model.version)
        dvc_lock = config.ROOT / "dvc.lock"
        if dvc_lock.exists():
            mlflow.log_artifact(str(dvc_lock))  # ties this run to the exact data version
        if fig_path.exists():
            mlflow.log_artifact(str(fig_path))
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=RiskPyfunc(),
            artifacts={"bundle": str(config.BUNDLE_PATH)},
            registered_model_name=config.REGISTERED_MODEL,
            pip_requirements=["lightgbm", "scikit-learn", "pandas", "numpy", "joblib"],
            code_paths=[str(config.ROOT / "src" / "routeguard")],
        )
    # Stages are deprecated in MLflow; an alias is the modern way to say "this is live".
    MlflowClient().set_registered_model_alias(
        config.REGISTERED_MODEL, "champion", info.registered_model_version
    )
    log.info("registered %s v%s as @champion", config.REGISTERED_MODEL, info.registered_model_version)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=None)
    ap.add_argument("--no-mlflow", action="store_true")
    args = ap.parse_args()
    run(n_trials=args.n_trials, use_mlflow=not args.no_mlflow)


if __name__ == "__main__":
    main()
