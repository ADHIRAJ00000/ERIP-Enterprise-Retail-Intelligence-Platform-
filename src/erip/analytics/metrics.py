"""
Business metrics & analytics engine.
====================================
Computes the full analytical layer that powers the executive dashboard and
the written insight report. Every function answers a specific business
question and returns plain, JSON-serialisable Python types.

Analyses implemented
---------------------
Executive KPIs · monthly trend & YoY · RFM segmentation · cohort retention ·
geographic performance · category / product ABC (Pareto) · channel mix ·
marketing ROAS & funnel · returns & quality · 6-month revenue forecast ·
driver correlations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from erip.analytics.features import revenue_orders
from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="analytics.log")


def _order_items_enriched(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Order items restricted to realised-revenue orders, with product category joined."""
    items = tables["fact_order_items"]
    orders = tables["fact_orders"][["order_id", "customer_id", "store_id", "channel", "order_status"]]
    products = tables["dim_products"][["product_id", "category", "brand"]]
    rev = revenue_orders(tables["fact_orders"])["order_id"]
    df = items[items["order_id"].isin(set(rev))].merge(
        orders, on="order_id", how="left"
    ).merge(products, on="product_id", how="left")
    return df


# ---------------------------------------------------------------------------
# 1. Executive KPIs
# ---------------------------------------------------------------------------
def executive_kpis(tables, items_enriched, monthly) -> dict:
    revenue = float(items_enriched["line_revenue"].sum())
    profit = float(items_enriched["line_profit"].sum())
    rev_orders = revenue_orders(tables["fact_orders"])
    n_orders = int(rev_orders["order_id"].nunique())
    n_customers = int(rev_orders["customer_id"].nunique())
    aov = revenue / n_orders if n_orders else 0.0

    # Repeat-purchase rate: share of customers with >1 revenue order.
    per_cust = rev_orders.groupby("customer_id")["order_id"].nunique()
    repeat_rate = float((per_cust > 1).mean() * 100)

    # Return rate: returns as share of revenue orders.
    n_returns = int(tables["fact_returns"]["order_id"].nunique()) if "fact_returns" in tables else 0
    return_rate = 100.0 * n_returns / n_orders if n_orders else 0.0

    # YoY growth: last full year vs prior.
    yearly = (
        rev_orders.assign(year=rev_orders["order_date"].dt.year)
        .groupby("year")["total_amount"].sum()
    )
    yoy = float((yearly.iloc[-1] / yearly.iloc[-2] - 1) * 100) if len(yearly) >= 2 else 0.0

    return {
        "total_revenue": revenue,
        "gross_profit": profit,
        "gross_margin_pct": 100.0 * profit / revenue if revenue else 0.0,
        "total_orders": n_orders,
        "unique_customers": n_customers,
        "avg_order_value": aov,
        "repeat_purchase_rate_pct": repeat_rate,
        "return_rate_pct": return_rate,
        "revenue_yoy_pct": yoy,
        "date_start": str(rev_orders["order_date"].min().date()),
        "date_end": str(rev_orders["order_date"].max().date()),
    }


# ---------------------------------------------------------------------------
# 2. Monthly trend
# ---------------------------------------------------------------------------
def monthly_trend(monthly: pd.DataFrame) -> list[dict]:
    out = monthly.copy()
    out["month"] = out["month"].dt.strftime("%Y-%m")
    for col in ("revenue_yoy_pct", "revenue_mom_pct"):
        out[col] = out[col].round(2).where(out[col].notna(), None)
    out["revenue"] = out["revenue"].round(2)
    return out.to_dict(orient="records")


# ---------------------------------------------------------------------------
# 3. RFM segmentation
# ---------------------------------------------------------------------------
def rfm_summary(customer_features: pd.DataFrame) -> list[dict]:
    seg = (
        customer_features.groupby("rfm_segment")
        .agg(
            customers=("customer_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            total_revenue=("monetary", "sum"),
            avg_monetary=("monetary", "mean"),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    total_rev = seg["total_revenue"].sum()
    seg["revenue_share_pct"] = 100.0 * seg["total_revenue"] / total_rev
    for c in ("avg_recency_days", "avg_frequency", "total_revenue", "avg_monetary", "revenue_share_pct"):
        seg[c] = seg[c].round(2)
    return seg.to_dict(orient="records")


# ---------------------------------------------------------------------------
# 4. Cohort retention (monthly signup cohorts)
# ---------------------------------------------------------------------------
def cohort_retention(customers, orders, max_periods: int = 12) -> dict:
    rev = revenue_orders(orders)
    cust = customers[["customer_id", "signup_date"]].copy()
    cust["cohort"] = cust["signup_date"].dt.to_period("M")
    df = rev.merge(cust, on="customer_id", how="inner")
    df["order_period"] = df["order_date"].dt.to_period("M")
    df["period_index"] = (
        (df["order_period"].dt.year - df["cohort"].dt.year) * 12
        + (df["order_period"].dt.month - df["cohort"].dt.month)
    )
    df = df[(df["period_index"] >= 0) & (df["period_index"] < max_periods)]

    cohort_sizes = cust.groupby("cohort")["customer_id"].nunique()
    active = df.groupby(["cohort", "period_index"])["customer_id"].nunique().unstack(fill_value=0)
    retention = active.div(cohort_sizes, axis=0) * 100

    # Keep the most recent 12 cohorts for a readable heatmap.
    retention = retention.tail(12)
    return {
        "cohorts": [str(c) for c in retention.index],
        "periods": [int(p) for p in retention.columns],
        "matrix": retention.round(1).where(retention.notna(), None).values.tolist(),
        "cohort_sizes": [int(cohort_sizes.get(c, 0)) for c in retention.index],
    }


# ---------------------------------------------------------------------------
# 5. Geographic performance
# ---------------------------------------------------------------------------
def geographic_performance(tables, items_enriched) -> list[dict]:
    orders = revenue_orders(tables["fact_orders"])
    cust_country = tables["dim_customers"][["customer_id", "country"]]
    o = orders.merge(cust_country, on="customer_id", how="left")
    geo = (
        o.groupby("country")
        .agg(revenue=("total_amount", "sum"), orders=("order_id", "nunique"),
             customers=("customer_id", "nunique"))
        .reset_index()
    )
    geo["avg_order_value"] = geo["revenue"] / geo["orders"]
    geo["revenue_per_customer"] = geo["revenue"] / geo["customers"]
    total = geo["revenue"].sum()
    geo["revenue_share_pct"] = 100.0 * geo["revenue"] / total
    geo = geo.sort_values("revenue", ascending=False)
    for c in ("revenue", "avg_order_value", "revenue_per_customer", "revenue_share_pct"):
        geo[c] = geo[c].round(2)
    return geo.to_dict(orient="records")


# ---------------------------------------------------------------------------
# 6. Category performance + product ABC / Pareto
# ---------------------------------------------------------------------------
def category_performance(items_enriched) -> list[dict]:
    cat = (
        items_enriched.groupby("category")
        .agg(revenue=("line_revenue", "sum"), profit=("line_profit", "sum"),
             units=("quantity", "sum"))
        .reset_index()
    )
    cat["margin_pct"] = 100.0 * cat["profit"] / cat["revenue"]
    total = cat["revenue"].sum()
    cat["revenue_share_pct"] = 100.0 * cat["revenue"] / total
    cat = cat.sort_values("revenue", ascending=False)
    for c in ("revenue", "profit", "margin_pct", "revenue_share_pct"):
        cat[c] = cat[c].round(2)
    cat["units"] = cat["units"].astype(int)
    return cat.to_dict(orient="records")


def product_abc(items_enriched, products) -> dict:
    prod = (
        items_enriched.groupby("product_id")
        .agg(revenue=("line_revenue", "sum"), profit=("line_profit", "sum"))
        .reset_index()
        .merge(products[["product_id", "product_name", "category"]], on="product_id", how="left")
        .sort_values("revenue", ascending=False)
    )
    prod["cum_revenue_pct"] = 100.0 * prod["revenue"].cumsum() / prod["revenue"].sum()
    prod["abc_class"] = np.select(
        [prod["cum_revenue_pct"] <= 80, prod["cum_revenue_pct"] <= 95],
        ["A", "B"], default="C",
    )
    abc = (
        prod.groupby("abc_class")
        .agg(products=("product_id", "count"), revenue=("revenue", "sum"))
        .reset_index()
    )
    abc["product_share_pct"] = 100.0 * abc["products"] / abc["products"].sum()
    abc["revenue_share_pct"] = 100.0 * abc["revenue"] / abc["revenue"].sum()
    top = prod.head(10)[["product_name", "category", "revenue", "profit"]].round(2)
    return {
        "abc_summary": abc.round(2).to_dict(orient="records"),
        "top_products": top.to_dict(orient="records"),
        "n_products_sold": int(prod.shape[0]),
    }


# ---------------------------------------------------------------------------
# 7. Channel mix
# ---------------------------------------------------------------------------
def channel_mix(tables) -> list[dict]:
    orders = revenue_orders(tables["fact_orders"])
    ch = (
        orders.groupby("channel")
        .agg(revenue=("total_amount", "sum"), orders=("order_id", "nunique"))
        .reset_index()
    )
    ch["avg_order_value"] = ch["revenue"] / ch["orders"]
    ch["revenue_share_pct"] = 100.0 * ch["revenue"] / ch["revenue"].sum()
    for c in ("revenue", "avg_order_value", "revenue_share_pct"):
        ch[c] = ch[c].round(2)
    return ch.sort_values("revenue", ascending=False).to_dict(orient="records")


# ---------------------------------------------------------------------------
# 8. Marketing ROAS & funnel
# ---------------------------------------------------------------------------
def marketing_performance(tables) -> dict:
    if "fact_marketing_campaigns" not in tables:
        return {}
    m = tables["fact_marketing_campaigns"]
    by_channel = (
        m.groupby("channel")
        .agg(spend=("budget_usd", "sum"), revenue=("revenue_generated_usd", "sum"),
             impressions=("impressions", "sum"), clicks=("clicks", "sum"),
             conversions=("conversions", "sum"), campaigns=("campaign_id", "count"))
        .reset_index()
    )
    by_channel["roas"] = by_channel["revenue"] / by_channel["spend"]
    by_channel["ctr_pct"] = 100.0 * by_channel["clicks"] / by_channel["impressions"]
    by_channel["cvr_pct"] = 100.0 * by_channel["conversions"] / by_channel["clicks"]
    by_channel = by_channel.sort_values("roas", ascending=False)
    for c in ("spend", "revenue", "roas", "ctr_pct", "cvr_pct"):
        by_channel[c] = by_channel[c].round(2)

    funnel = {
        "impressions": int(m["impressions"].sum()),
        "clicks": int(m["clicks"].sum()),
        "conversions": int(m["conversions"].sum()),
        "total_spend": round(float(m["budget_usd"].sum()), 2),
        "total_revenue": round(float(m["revenue_generated_usd"].sum()), 2),
        "blended_roas": round(float(m["revenue_generated_usd"].sum() / m["budget_usd"].sum()), 2),
    }
    return {"by_channel": by_channel.to_dict(orient="records"), "funnel": funnel}


# ---------------------------------------------------------------------------
# 9. Returns & quality
# ---------------------------------------------------------------------------
def returns_analysis(tables) -> dict:
    if "fact_returns" not in tables:
        return {}
    r = tables["fact_returns"]
    by_reason = (
        r.groupby("return_reason")
        .agg(returns=("return_id", "count"), refund_amount=("refund_amount", "sum"))
        .reset_index()
        .sort_values("returns", ascending=False)
    )
    by_reason["share_pct"] = (100.0 * by_reason["returns"] / by_reason["returns"].sum()).round(2)
    by_reason["refund_amount"] = by_reason["refund_amount"].round(2)
    return {
        "total_returns": int(len(r)),
        "total_refunds": round(float(r["refund_amount"].sum()), 2),
        "restock_rate_pct": round(float(r["restocked"].mean() * 100), 2) if "restocked" in r else None,
        "by_reason": by_reason.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# 10. Forecast (seasonal-naive + linear trend blend)
# ---------------------------------------------------------------------------
def revenue_forecast(monthly: pd.DataFrame, horizon: int = 6) -> list[dict]:
    ts = monthly.dropna(subset=["revenue"]).reset_index(drop=True)
    y = ts["revenue"].values
    n = len(y)
    x = np.arange(n)
    # Linear trend via least squares.
    slope, intercept = np.polyfit(x, y, 1)
    # Multiplicative seasonal factors from the last 24 months vs their trend.
    trend_fit = slope * x + intercept
    seasonal = np.ones(12)
    resid = y / np.where(trend_fit == 0, 1, trend_fit)
    for m in range(12):
        month_idx = [i for i in range(n) if ts["month"].dt.month.iloc[i] == (m + 1)]
        if month_idx:
            seasonal[m] = np.mean(resid[month_idx])
    out = []
    last_month = ts["month"].iloc[-1]
    for h in range(1, horizon + 1):
        fx = n - 1 + h
        fut_month = (last_month + pd.DateOffset(months=h))
        base = slope * fx + intercept
        forecast = base * seasonal[(fut_month.month - 1)]
        out.append({
            "month": fut_month.strftime("%Y-%m"),
            "revenue_forecast": round(float(max(forecast, 0)), 2),
            "type": "forecast",
        })
    return out


# ---------------------------------------------------------------------------
# 11. Driver correlations
# ---------------------------------------------------------------------------
def driver_correlations(tables, monthly) -> list[dict]:
    """Correlate monthly revenue with marketing spend and web traffic where available."""
    out = []
    base = monthly.set_index(monthly["month"].dt.to_period("M"))["revenue"]

    if "fact_marketing_campaigns" in tables:
        m = tables["fact_marketing_campaigns"].copy()
        m["period"] = m["start_date"].dt.to_period("M")
        spend = m.groupby("period")["budget_usd"].sum()
        joined = pd.concat([base, spend], axis=1, join="inner").dropna()
        if len(joined) > 3:
            out.append({"driver": "Marketing spend", "correlation": round(float(joined.corr().iloc[0, 1]), 3),
                        "months": int(len(joined))})

    if "fact_website_traffic" in tables:
        w = tables["fact_website_traffic"].copy()
        w["period"] = w["date"].dt.to_period("M")
        visits = w.groupby("period")["visitors"].sum()
        joined = pd.concat([base, visits], axis=1, join="inner").dropna()
        if len(joined) > 3:
            out.append({"driver": "Website visitors", "correlation": round(float(joined.corr().iloc[0, 1]), 3),
                        "months": int(len(joined))})
    return out


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def compute_all(tables, customer_features, monthly) -> dict:
    """Run every analysis and assemble the master metrics dict."""
    logger.info("Computing business metrics...")
    items_enriched = _order_items_enriched(tables)
    results = {
        "executive_kpis": executive_kpis(tables, items_enriched, monthly),
        "monthly_trend": monthly_trend(monthly),
        "rfm_segments": rfm_summary(customer_features),
        "cohort_retention": cohort_retention(tables["dim_customers"], tables["fact_orders"]),
        "geographic": geographic_performance(tables, items_enriched),
        "category_performance": category_performance(items_enriched),
        "product_abc": product_abc(items_enriched, tables["dim_products"]),
        "channel_mix": channel_mix(tables),
        "marketing": marketing_performance(tables),
        "returns": returns_analysis(tables),
        "forecast": revenue_forecast(monthly),
        "correlations": driver_correlations(tables, monthly),
    }
    logger.info("Metrics computation complete (%d analysis blocks).", len(results))
    return results
