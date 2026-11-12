import pytest

from routeguard import build_data, config, synthetic, train


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    """Synthetic Olist data -> processed tables -> trained bundle, all inside a temp folder."""
    root = tmp_path_factory.mktemp("rg")
    mp = pytest.MonkeyPatch()
    raw = root / "raw"
    synthetic.write(raw, n_orders=3500, seed=3)
    patches = {
        "DATA_RAW": raw,
        "DATA_PROCESSED": root / "processed",
        "ORDERS_CSV": root / "processed" / "orders.csv",
        "GEO_CSV": root / "processed" / "geo.csv",
        "MODELS_DIR": root / "models",
        "REPORTS_DIR": root / "reports",
        "BUNDLE_PATH": root / "models" / "bundle.joblib",
        "DB_PATH": root / "logs" / "predictions.db",
    }
    for k, v in patches.items():
        mp.setattr(config, k, v)
    build_data.main()
    metrics = train.run(n_trials=2, use_mlflow=False)
    yield {"root": root, "metrics": metrics}
    mp.undo()


@pytest.fixture()
def order():
    return {
        "order_id": "T-1",
        "order_purchase_timestamp": "2018-03-14T10:23:00",
        "order_estimated_delivery_date": "2018-03-30T00:00:00",
        "customer_state": "RJ",
        "seller_state": "SP",
        "customer_zip_code_prefix": 10000 + 1 * 5000 + 137,
        "seller_zip_code_prefix": 10000,
        "total_items": 2,
        "total_item_price": 150.0,
        "total_freight": 25.5,
        "avg_item_price": 75.0,
        "avg_product_weight_g": 800,
        "avg_volume_cm3": 6000,
        "max_installments": 3,
        "total_payment_value": 175.5,
        "payment_types_used": "credit_card",
    }
