import numpy as np
import pandas as pd
import pytest

from routeguard import config
from routeguard.features import haversine_km, seller_history_time_aware


def test_haversine_sao_paulo_to_rio():
    d = haversine_km(-23.55, -46.63, -22.91, -43.17)
    assert 340 < d < 380


def test_seller_history_never_looks_into_the_future():
    t = pd.to_datetime
    df = pd.DataFrame(
        {
            "seller_id": ["a", "a", "a"],
            config.TIME_COL: t(["2018-01-01", "2018-01-05", "2018-02-01"]),
            config.DELIVERED_COL: t(["2018-01-10", "2018-01-20", "2018-02-15"]),
            config.TARGET: [1, 0, 1],
        }
    )
    out = seller_history_time_aware(df, prior=0.1, strength=10)
    # order 0: nothing delivered yet
    assert out.seller_n_orders.iloc[0] == 0 and out.seller_late_rate.iloc[0] == pytest.approx(0.1)
    # order 1 (Jan 5): order 0 is still in transit (delivered Jan 10) -> still nothing known
    assert out.seller_n_orders.iloc[1] == 0
    # order 2 (Feb 1): orders 0 and 1 delivered; one of them late
    assert out.seller_n_orders.iloc[2] == 2
    assert out.seller_late_rate.iloc[2] == pytest.approx((1 + 0.1 * 10) / (2 + 10))


def test_serving_features_do_not_use_delivery_columns():
    forbidden = {config.DELIVERED_COL, config.TARGET, "delivery_days"}
    assert forbidden.isdisjoint(config.ALL_FEATURES)
    assert np.isin(config.CATEGORICAL_FEATURES, config.ALL_FEATURES).all()
