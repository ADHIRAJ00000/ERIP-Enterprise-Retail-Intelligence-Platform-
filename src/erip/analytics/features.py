"""
Feature engineering layer.
==========================
Transforms the normalised star schema into analysis-ready base tables:

* `build_customer_features`  -> one row per customer with RFM inputs,
  tenure, AOV, category affinity and an RFM-based value segment.
* `build_monthly_revenue`    -> monthly revenue/profit/order time series.

These base tables are consumed by both the metrics engine and the ML/
forecasting layer, so feature logic lives in exactly one place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="analytics.log")

# Order statuses that represent realised, revenue-generating demand.
REVENUE_STATUSES = ("Completed", "Shipped")


def revenue_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Return only orders that count as realised revenue (exclude cancels/refunds)."""
    return orders[orders["order_status"].isin(REVENUE_STATUSES)].copy()


def build_customer_features(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    snapshot_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Build a customer-level feature table with RFM scores and value segments.

    RFM is scored 1-5 per dimension using quintiles; recency is reversed so
    that a *recent* customer scores 5. The 11-cell segmentation collapses the
    25 RFM combinations into named, actionable segments used across the
    dashboard and CRM recommendations.
    """
    rev = revenue_orders(orders)
    if snapshot_date is None:
        # Analyse "as of" the day after the last transaction.
        snapshot_date = rev["order_date"].max() + pd.Timedelta(days=1)

    agg = rev.groupby("customer_id").agg(
        recency_days=("order_date", lambda s: (snapshot_date - s.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("total_amount", "sum"),
        first_order=("order_date", "min"),
        last_order=("order_date", "max"),
        avg_order_value=("total_amount", "mean"),
    )

    feat = customers.merge(agg, left_on="customer_id", right_index=True, how="left")
    # Customers who never placed a revenue order.
    feat["frequency"] = feat["frequency"].fillna(0).astype(int)
    feat["monetary"] = feat["monetary"].fillna(0.0)
    feat["avg_order_value"] = feat["avg_order_value"].fillna(0.0)
    feat["recency_days"] = feat["recency_days"].fillna(
        (snapshot_date - feat["signup_date"]).dt.days
    )
    feat["tenure_days"] = (snapshot_date - feat["signup_date"]).dt.days

    buyers = feat["frequency"] > 0

    def _score(series: pd.Series, reverse: bool = False) -> pd.Series:
        """Quintile score 1-5 over buyers only; non-buyers get 0."""
        s = pd.Series(0, index=series.index, dtype=int)
        ranks = series[buyers].rank(method="first")
        labels = [5, 4, 3, 2, 1] if reverse else [1, 2, 3, 4, 5]
        s.loc[buyers] = pd.qcut(ranks, 5, labels=labels).astype(int)
        return s

    feat["R"] = _score(feat["recency_days"], reverse=True)
    feat["F"] = _score(feat["frequency"])
    feat["M"] = _score(feat["monetary"])
    feat["rfm_score"] = feat["R"] + feat["F"] + feat["M"]

    feat["rfm_segment"] = np.select(
        [
            ~buyers,
            (feat["R"] >= 4) & (feat["F"] >= 4) & (feat["M"] >= 4),
            (feat["R"] >= 3) & (feat["F"] >= 3) & (feat["M"] >= 4),
            (feat["R"] >= 4) & (feat["F"] <= 2),
            (feat["R"] >= 3) & (feat["F"] >= 3),
            (feat["R"] <= 2) & (feat["F"] >= 3) & (feat["M"] >= 3),
            (feat["R"] <= 2) & (feat["M"] >= 4),
            (feat["R"] <= 2) & (feat["F"] <= 2),
        ],
        [
            "Never Purchased",
            "Champions",
            "Loyal Customers",
            "New Customers",
            "Potential Loyalists",
            "At Risk",
            "Can't Lose Them",
            "Hibernating",
        ],
        default="Needs Attention",
    )
    return feat


def build_monthly_revenue(orders: pd.DataFrame) -> pd.DataFrame:
    """Monthly revenue / profit-proxy / order-count time series from revenue orders."""
    rev = revenue_orders(orders)
    rev = rev.assign(month=rev["order_date"].dt.to_period("M").dt.to_timestamp())
    monthly = (
        rev.groupby("month")
        .agg(revenue=("total_amount", "sum"), orders=("order_id", "nunique"))
        .reset_index()
        .sort_values("month")
    )
    monthly["revenue_yoy_pct"] = monthly["revenue"].pct_change(12) * 100
    monthly["revenue_mom_pct"] = monthly["revenue"].pct_change() * 100
    return monthly
