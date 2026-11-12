"""Data-quality gate (Great Expectations). The DVC pipeline stops here if the data looks wrong.

python -m routeguard.validate
"""

from __future__ import annotations

import logging
import sys

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from routeguard import config

log = logging.getLogger("validate")


def build_suite(min_rows: int) -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name="orders_suite")
    expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=min_rows),
        gxe.ExpectColumnValuesToNotBeNull(column="order_id"),
        gxe.ExpectColumnValuesToBeUnique(column="order_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="seller_id"),
        gxe.ExpectColumnValuesToNotBeNull(column="customer_zip_code_prefix", mostly=0.999),
        gxe.ExpectColumnValuesToBeInSet(column=config.TARGET, value_set=[0, 1]),
        gxe.ExpectColumnValuesToBeInSet(column="customer_state", value_set=config.BR_STATES, mostly=0.999),
        gxe.ExpectColumnValuesToBeInSet(column="seller_state", value_set=config.BR_STATES, mostly=0.999),
        gxe.ExpectColumnValuesToBeBetween(
            column="total_item_price", min_value=0, max_value=30000, mostly=0.999
        ),
        gxe.ExpectColumnValuesToBeBetween(column="total_freight", min_value=0, max_value=5000, mostly=0.999),
        gxe.ExpectColumnValuesToBeBetween(column="promised_days", min_value=0.5, max_value=200, mostly=0.99),
        gxe.ExpectColumnValuesToBeBetween(column="delivery_days", min_value=0, max_value=300, mostly=0.99),
        # A late rate far outside this band means the label logic or the data changed.
        gxe.ExpectColumnMeanToBeBetween(column=config.TARGET, min_value=0.02, max_value=0.30),
    ]
    for e in expectations:
        suite.add_expectation(e)
    return suite


def validate_orders(df: pd.DataFrame, min_rows: int = 1000) -> tuple[bool, list[str]]:
    df = df.copy()
    t = pd.to_datetime(df[config.TIME_COL])
    df["promised_days"] = (pd.to_datetime(df[config.ESTIMATED_COL]) - t).dt.total_seconds() / 86400
    df["delivery_days"] = (pd.to_datetime(df[config.DELIVERED_COL]) - t).dt.total_seconds() / 86400

    context = gx.get_context(mode="ephemeral")
    batch = (
        context.data_sources.add_pandas("orders")
        .add_dataframe_asset("orders_df")
        .add_batch_definition_whole_dataframe("whole")
        .get_batch(batch_parameters={"dataframe": df})
    )
    result = batch.validate(build_suite(min_rows))
    failures = [
        f"{r.expectation_config.type}: {r.expectation_config.kwargs.get('column', 'table')}"
        for r in result.results
        if not r.success
    ]
    return bool(result.success), failures


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    df = pd.read_csv(config.ORDERS_CSV)
    ok, failures = validate_orders(df)
    if ok:
        log.info("Data validation passed (%s rows).", f"{len(df):,}")
        return
    for f in failures:
        log.error("FAILED  %s", f)
    sys.exit(1)


if __name__ == "__main__":
    main()
