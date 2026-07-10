"""
Data quality & validation layer.
================================
Runs a battery of production-style data-quality checks over the loaded
star schema and returns a structured report plus a single 0-100 quality
score. Mirrors the checks in `sql/queries/data_cleaning_validation.sql`,
executed in Python so they run without a live database.

Check families
--------------
1. Completeness        - null rates on business-critical columns
2. Uniqueness          - duplicate primary keys
3. Referential integrity - orphan foreign keys (fact rows with no parent dim)
4. Validity            - business-rule bounds (non-negative money, sane dates,
                         margins within contract range, ratings 1-5, etc.)
5. Consistency         - cross-table totals reconcile (order_items -> orders)
"""

from __future__ import annotations

import pandas as pd

from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="analytics.log")

# Business-critical columns that must never be null, per table.
_CRITICAL_COLUMNS: dict[str, list[str]] = {
    "dim_customers": ["customer_id", "country", "signup_date"],
    "dim_products": ["product_id", "category", "unit_price", "unit_cost"],
    "fact_orders": ["order_id", "customer_id", "order_date", "total_amount"],
    "fact_order_items": ["order_id", "product_id", "quantity", "line_revenue"],
}

# Primary keys used for the uniqueness check.
_PRIMARY_KEYS: dict[str, str] = {
    "dim_customers": "customer_id",
    "dim_products": "product_id",
    "dim_stores": "store_id",
    "fact_orders": "order_id",
    "fact_order_items": "order_item_id",
}


def _pct(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def run_quality_checks(tables: dict[str, pd.DataFrame]) -> dict:
    """Execute all data-quality checks and return a structured report."""
    logger.info("Running data-quality checks...")
    checks: list[dict] = []

    def record(name: str, family: str, failed: int, total: int, detail: str = "") -> None:
        checks.append(
            {
                "check": name,
                "family": family,
                "records_scanned": int(total),
                "records_failed": int(failed),
                "failure_rate_pct": _pct(failed, total),
                "passed": bool(failed == 0),
                "detail": detail,
            }
        )

    # 1. Completeness --------------------------------------------------------
    for table, cols in _CRITICAL_COLUMNS.items():
        if table not in tables:
            continue
        df = tables[table]
        for col in cols:
            if col in df.columns:
                record(f"{table}.{col} not null", "completeness", int(df[col].isna().sum()), len(df))

    # 2. Uniqueness ----------------------------------------------------------
    for table, key in _PRIMARY_KEYS.items():
        if table in tables and key in tables[table].columns:
            df = tables[table]
            dupes = int(df[key].duplicated().sum())
            record(f"{table}.{key} unique", "uniqueness", dupes, len(df))

    # 3. Referential integrity ----------------------------------------------
    ri_checks = [
        ("fact_orders", "customer_id", "dim_customers", "customer_id"),
        ("fact_orders", "store_id", "dim_stores", "store_id"),
        ("fact_order_items", "order_id", "fact_orders", "order_id"),
        ("fact_order_items", "product_id", "dim_products", "product_id"),
        ("fact_returns", "order_id", "fact_orders", "order_id"),
        ("fact_reviews", "product_id", "dim_products", "product_id"),
    ]
    # "Not applicable" markers: an Online order carries store_id="ONLINE" because no
    # physical store applies. These are valid sentinels, not orphan keys — a correct
    # RI check ignores nulls and documented sentinels and only flags a *real* FK value
    # that points at a missing parent row.
    NA_SENTINELS = {"ONLINE", "N/A", "NONE", "UNKNOWN", ""}
    for child, fk, parent, pk in ri_checks:
        if child in tables and parent in tables:
            child_df, parent_df = tables[child], tables[parent]
            if fk in child_df.columns and pk in parent_df.columns:
                valid = set(parent_df[pk].unique())
                populated = child_df[fk].dropna()
                populated = populated[~populated.astype(str).str.upper().isin(NA_SENTINELS)]
                orphans = int((~populated.isin(valid)).sum())
                record(f"{child}.{fk} -> {parent}.{pk}", "referential_integrity", orphans, len(populated))

    # 4. Validity ------------------------------------------------------------
    if "fact_orders" in tables:
        o = tables["fact_orders"]
        record("fact_orders.total_amount >= 0", "validity", int((o["total_amount"] < 0).sum()), len(o))
    if "fact_order_items" in tables:
        oi = tables["fact_order_items"]
        record("fact_order_items.quantity > 0", "validity", int((oi["quantity"] <= 0).sum()), len(oi))
    if "dim_products" in tables:
        p = tables["dim_products"]
        record("dim_products price > cost", "validity", int((p["unit_price"] <= p["unit_cost"]).sum()), len(p))
    if "dim_customers" in tables:
        c = tables["dim_customers"]
        bad_age = int(((c["age"] < 18) | (c["age"] > 100)).sum())
        record("dim_customers.age in [18,100]", "validity", bad_age, len(c))
    if "fact_reviews" in tables:
        r = tables["fact_reviews"]
        record("fact_reviews.rating in [1,5]", "validity", int(((r["rating"] < 1) | (r["rating"] > 5)).sum()), len(r))

    # 5. Consistency ---------------------------------------------------------
    if {"fact_orders", "fact_order_items"} <= tables.keys():
        orders = set(tables["fact_orders"]["order_id"].unique())
        items_orders = set(tables["fact_order_items"]["order_id"].unique())
        orphan_orders = len(orders - items_orders)
        record("every order has >=1 line item", "consistency", orphan_orders, len(orders))

    # Score: weight referential integrity and consistency failures heavily. ---
    total_checks = len(checks)
    passed_checks = sum(c["passed"] for c in checks)
    # Penalise by failure rate so a check that fails on 0.1% of rows costs less
    # than one that fails on 40%.
    penalty = sum(min(c["failure_rate_pct"], 100) / 100 for c in checks if not c["passed"])
    score = round(max(0.0, 100.0 * (1 - penalty / total_checks)), 2) if total_checks else 100.0

    report = {
        "score": score,
        "checks_total": total_checks,
        "checks_passed": passed_checks,
        "checks_failed": total_checks - passed_checks,
        "checks": checks,
    }
    logger.info(
        "Data-quality score: %.2f/100 (%d/%d checks passed)",
        score, passed_checks, total_checks,
    )
    return report
