"""
Transactional fact tables: orders, order_items, payments, returns, shipping.

This is the core of the platform's data volume. Order dates are generated
with realistic seasonality (weekday effect, holiday spikes, year-over-year
growth trend) rather than uniform random dates, so downstream time-series
and forecasting work has real signal to find.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import (
    PAYMENT_METHODS, ORDER_STATUSES, SHIPPING_CARRIERS, RETURN_REASONS, US_HOLIDAYS,
)
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def _seasonal_date_weights(date_range: pd.DatetimeIndex) -> np.ndarray:
    """
    Build a sampling-weight array over `date_range` that encodes:
      - mild year-over-year growth trend
      - weekday vs weekend lift (Fri/Sat higher)
      - holiday season spike (Nov-Dec) and post-holiday slump (Jan)
    """
    years = date_range.year.values
    yoy_growth = 1.0 + (years - years.min()) * 0.07          # ~7% YoY growth

    dow = date_range.dayofweek.values
    dow_weight = np.where(np.isin(dow, [4, 5]), 1.35, 1.0)    # Fri/Sat boost
    dow_weight = np.where(dow == 6, 0.85, dow_weight)         # Sunday dip

    month = date_range.month.values
    month_weight = np.ones(len(date_range))
    month_weight[np.isin(month, [11, 12])] = 1.6              # holiday shopping season
    month_weight[month == 1] = 0.75                           # post-holiday slump
    month_weight[np.isin(month, [6, 7])] = 1.15                # summer sales bump

    weights = yoy_growth * dow_weight * month_weight
    return weights / weights.sum()


def generate_orders_and_items(
    customers_df: pd.DataFrame,
    products_df: pd.DataFrame,
    stores_df: pd.DataFrame,
    n_orders: int = None,
    seed: int = None,
):
    """
    Generate the orders fact table and the order_items fact table (grain:
    one row per product per order).

    Returns:
        (orders_df, order_items_df)
    """
    n_orders_target = n_orders or SCALE.n_orders
    rng = np.random.default_rng((seed or SCALE.random_seed) + 5)
    n_cust = len(customers_df)
    logger.info(f"Generating ~{n_orders_target:,} orders with a per-customer lifecycle model...")

    # ------------------------------------------------------------------
    # Customer lifecycle model (this is what gives the data real signal).
    #
    # Instead of assigning orders to customers uniformly at random, each
    # customer gets:
    #   1. a latent PURCHASE PROPENSITY (heavy-tailed) -> a few "whale"
    #      customers place many orders while most place few. This makes RFM
    #      frequency/monetary, customer ABC and CLV meaningful.
    #   2. a CHURN LIFECYCLE -> low-propensity customers are likelier to lapse
    #      and stop ordering partway through their tenure. This makes recency
    #      predictive of churn and gives cohort-retention real structure.
    # Orders are only placed inside each customer's active window
    # [signup_date, active_until], so (unlike before) no order predates signup.
    # ------------------------------------------------------------------
    end = np.datetime64(SCALE.end_date, "D")
    signup = customers_df["signup_date"].values.astype("datetime64[D]")

    propensity = rng.gamma(shape=0.85, scale=1.0, size=n_cust) + 0.02
    p_norm = propensity / propensity.max()

    churn_prob = np.clip(0.60 * (1 - p_norm) ** 1.3, 0.03, 0.60)
    is_churner = rng.random(n_cust) < churn_prob
    span_days = np.clip(((end - signup) / np.timedelta64(1, "D")).astype(int), 1, None)
    active_frac = np.where(is_churner, rng.uniform(0.15, 0.85, size=n_cust), 1.0)
    active_until = signup + (span_days * active_frac).astype("timedelta64[D]")

    # Expected orders per customer ~ propensity x active tenure, then Poisson draw.
    active_years = np.clip(((active_until - signup) / np.timedelta64(365, "D")), 0.05, None)
    raw_rate = propensity * active_years
    lam = raw_rate * (n_orders_target / raw_rate.sum())
    n_per_cust = rng.poisson(lam)
    n_orders = int(n_per_cust.sum())
    logger.info(f"  {int((n_per_cust == 0).sum()):,} customers never purchase; "
                f"{int(is_churner.sum()):,} are lapsing; generating {n_orders:,} orders")

    customer_idx = np.repeat(np.arange(n_cust), n_per_cust)

    # Order dates: seasonal distribution, rejection-sampled into each customer's
    # active window (falls back to uniform-in-window for the few stragglers).
    date_range = pd.date_range(SCALE.start_date, SCALE.end_date, freq="D")
    weights = _seasonal_date_weights(date_range)
    date_pool = date_range.values.astype("datetime64[D]")
    cust_start, cust_end = signup[customer_idx], active_until[customer_idx]
    order_dates_d = np.empty(n_orders, dtype="datetime64[D]")
    todo = np.arange(n_orders)
    for _ in range(6):
        draw = rng.choice(date_pool, size=len(todo), p=weights)
        ok = (draw >= cust_start[todo]) & (draw <= cust_end[todo])
        order_dates_d[todo[ok]] = draw[ok]
        todo = todo[~ok]
        if len(todo) == 0:
            break
    if len(todo):
        w = np.clip(((cust_end[todo] - cust_start[todo]) / np.timedelta64(1, "D")).astype(int), 0, None)
        order_dates_d[todo] = cust_start[todo] + (rng.random(len(todo)) * (w + 1)).astype(int).astype("timedelta64[D]")

    order_dates = order_dates_d.astype("datetime64[ns]")
    customer_ids = customers_df["customer_id"].values[customer_idx]

    # ~34% of orders are placed online, 66% in-store (drives channel & store_id logic)
    is_online = rng.choice([True, False], size=n_orders, p=[0.34, 0.66])
    store_ids = np.where(
        is_online, "ONLINE",
        rng.choice(stores_df["store_id"], size=n_orders)
    )

    statuses = rng.choice(
        ORDER_STATUSES, size=n_orders, p=[0.74, 0.08, 0.05, 0.05, 0.05, 0.03]
    )

    orders_df = pd.DataFrame({
        "order_id": [f"ORD{idx:09d}" for idx in range(1, n_orders + 1)],
        "customer_id": customer_ids,
        "store_id": store_ids,
        "order_date": order_dates,
        "channel": np.where(is_online, "Online", "In-Store"),
        "order_status": statuses,
        "payment_method": rng.choice(PAYMENT_METHODS, size=n_orders),
    })

    # --- order_items: 1-5 items per order, Poisson-ish skew toward 1-3 ---
    items_per_order = rng.choice([1, 2, 3, 4, 5], size=n_orders, p=[0.38, 0.28, 0.18, 0.10, 0.06])
    total_items = int(items_per_order.sum())
    logger.info(f"Generating {total_items:,} order line items...")

    order_id_repeated = np.repeat(orders_df["order_id"].values, items_per_order)
    order_date_repeated = np.repeat(orders_df["order_date"].values, items_per_order)

    product_sample_idx = rng.integers(0, len(products_df), size=total_items)
    sampled_products = products_df.iloc[product_sample_idx].reset_index(drop=True)

    quantities = rng.choice([1, 2, 3, 4], size=total_items, p=[0.62, 0.24, 0.10, 0.04])
    discount_pct = rng.choice([0, 0, 0, 5, 10, 15, 20, 25, 30], size=total_items) / 100.0

    unit_price = sampled_products["unit_price"].values
    line_revenue = np.round(unit_price * quantities * (1 - discount_pct), 2)
    unit_cost = sampled_products["unit_cost"].values
    line_cost = np.round(unit_cost * quantities, 2)

    order_items_df = pd.DataFrame({
        "order_item_id": [f"OI{idx:010d}" for idx in range(1, total_items + 1)],
        "order_id": order_id_repeated,
        "order_date": order_date_repeated,
        "product_id": sampled_products["product_id"].values,
        "quantity": quantities,
        "unit_price": unit_price,
        "discount_pct": discount_pct,
        "line_revenue": line_revenue,
        "line_cost": line_cost,
        "line_profit": np.round(line_revenue - line_cost, 2),
    })

    # Roll up order-level total_amount onto orders_df
    order_totals = order_items_df.groupby("order_id")["line_revenue"].sum().rename("total_amount")
    orders_df = orders_df.merge(order_totals, on="order_id", how="left")
    orders_df["total_amount"] = orders_df["total_amount"].fillna(0).round(2)

    logger.info(
        f"Order generation complete: {len(orders_df):,} orders, {len(order_items_df):,} line items, "
        f"total GMV ${orders_df['total_amount'].sum():,.0f}"
    )
    return orders_df, order_items_df


def generate_payments(orders_df: pd.DataFrame, seed: int = None) -> pd.DataFrame:
    """Generate the payments fact table (1 payment per completed/shipped/processing order)."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 6)
    payable = orders_df[orders_df["order_status"] != "Cancelled"].copy()
    logger.info(f"Generating {len(payable):,} payment records...")

    payment_status = rng.choice(
        ["Success", "Failed", "Pending", "Refunded"], size=len(payable), p=[0.93, 0.02, 0.02, 0.03]
    )

    df = pd.DataFrame({
        "payment_id": [f"PAY{idx:09d}" for idx in range(1, len(payable) + 1)],
        "order_id": payable["order_id"].values,
        "payment_date": payable["order_date"].values,
        "amount": payable["total_amount"].values,
        "payment_method": payable["payment_method"].values,
        "payment_status": payment_status,
        "transaction_fee_pct": rng.uniform(0.015, 0.035, size=len(payable)).round(4),
    })
    logger.info(f"Payment generation complete: {len(df):,} rows")
    return df


def generate_returns(orders_df: pd.DataFrame, order_items_df: pd.DataFrame, seed: int = None) -> pd.DataFrame:
    """Generate the returns fact table for a subset of delivered orders."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 7)

    returned_orders = orders_df[orders_df["order_status"] == "Returned"]
    eligible_items = order_items_df[order_items_df["order_id"].isin(returned_orders["order_id"])]
    # Sample which specific line items were the ones returned (not necessarily all lines in the order)
    n_returns = max(1, int(len(eligible_items) * 0.85))
    sampled = eligible_items.sample(n=min(n_returns, len(eligible_items)), random_state=int(seed or SCALE.random_seed))

    return_delay_days = rng.integers(1, 30, size=len(sampled))
    return_dates = pd.to_datetime(sampled["order_date"].values) + pd.to_timedelta(return_delay_days, unit="D")

    df = pd.DataFrame({
        "return_id": [f"RET{idx:08d}" for idx in range(1, len(sampled) + 1)],
        "order_id": sampled["order_id"].values,
        "order_item_id": sampled["order_item_id"].values,
        "return_date": return_dates,
        "return_reason": rng.choice(RETURN_REASONS, size=len(sampled)),
        "refund_amount": sampled["line_revenue"].values,
        "restocked": rng.choice([True, False], size=len(sampled), p=[0.7, 0.3]),
    })
    logger.info(f"Return generation complete: {len(df):,} rows")
    return df


def generate_shipping(orders_df: pd.DataFrame, seed: int = None) -> pd.DataFrame:
    """Generate the shipping fact table for online orders that were shipped/completed."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 8)
    shippable = orders_df[
        (orders_df["channel"] == "Online") & (orders_df["order_status"].isin(["Completed", "Shipped"]))
    ].copy()
    logger.info(f"Generating {len(shippable):,} shipping records...")

    transit_days = rng.integers(1, 9, size=len(shippable))
    ship_dates = pd.to_datetime(shippable["order_date"].values) + pd.to_timedelta(rng.integers(0, 2, size=len(shippable)), unit="D")
    delivery_dates = ship_dates + pd.to_timedelta(transit_days, unit="D")

    promised_days = rng.choice([3, 5, 7, 9], size=len(shippable), p=[0.15, 0.35, 0.35, 0.15])
    is_delayed = transit_days > promised_days

    df = pd.DataFrame({
        "shipment_id": [f"SHP{idx:09d}" for idx in range(1, len(shippable) + 1)],
        "order_id": shippable["order_id"].values,
        "carrier": rng.choice(SHIPPING_CARRIERS, size=len(shippable)),
        "ship_date": ship_dates,
        "delivery_date": delivery_dates,
        "promised_delivery_days": promised_days,
        "actual_transit_days": transit_days,
        "is_delayed": is_delayed,
        "shipping_cost": np.round(rng.uniform(2.5, 35, size=len(shippable)), 2),
    })
    logger.info(f"Shipping generation complete: {len(df):,} rows, delay rate {is_delayed.mean()*100:.1f}%")
    return df
