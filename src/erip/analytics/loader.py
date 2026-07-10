"""
Data loading layer for the ERIP analytics engine.
=================================================
Reads the raw star-schema tables (gzip CSV) into typed pandas DataFrames
with correct date parsing and lightweight memory optimisation, so every
downstream analytics module works from a single, consistent source of truth.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from erip.config.settings import DATA_RAW_DIR, DATA_SAMPLE_DIR
from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="analytics.log")

# Columns to parse as dates, per table. Anything not listed stays as-is.
_DATE_COLUMNS: dict[str, list[str]] = {
    "dim_customers": ["signup_date"],
    "dim_products": ["launch_date"],
    "dim_stores": ["opened_date"],
    "dim_employees": ["hire_date"],
    "dim_suppliers": ["contract_start_date"],
    "dim_coupons": ["issue_date", "expiry_date"],
    "dim_holiday_calendar": ["date"],
    "fact_orders": ["order_date"],
    "fact_order_items": ["order_date"],
    "fact_payments": ["payment_date"],
    "fact_returns": ["return_date"],
    "fact_shipping": ["ship_date", "delivery_date"],
    "fact_reviews": ["review_date"],
    "fact_marketing_campaigns": ["start_date", "end_date"],
    "fact_inventory": ["last_restocked_date"],
    "fact_website_traffic": ["date"],
    "fact_weather": ["date"],
    "fact_economic_indicators": ["month"],
}

TABLES = tuple(_DATE_COLUMNS.keys())


def load_table(name: str, sample: bool = False) -> pd.DataFrame:
    """Load a single star-schema table with correct date parsing."""
    source_dir = DATA_SAMPLE_DIR if sample else DATA_RAW_DIR
    path = Path(source_dir) / f"{name}.csv.gz"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python scripts/generate_data.py` first."
        )
    df = pd.read_csv(path, parse_dates=_DATE_COLUMNS.get(name, []))
    return df


def load_star_schema(sample: bool = False) -> dict[str, pd.DataFrame]:
    """
    Load every available star-schema table into a name -> DataFrame dict.

    The sample profile omits a few context tables; missing tables are skipped
    with a warning rather than raising, so the engine runs on either profile.
    """
    profile = "sample" if sample else "raw"
    logger.info("Loading star-schema tables (%s profile)...", profile)
    tables: dict[str, pd.DataFrame] = {}
    total_rows = 0
    for name in TABLES:
        try:
            df = load_table(name, sample=sample)
        except FileNotFoundError:
            logger.warning("  skipped %-28s (not present in %s profile)", name, profile)
            continue
        tables[name] = df
        total_rows += len(df)
        logger.info("  loaded %-28s %10s rows x %2d cols", name, f"{len(df):,}", df.shape[1])
    logger.info("Loaded %d tables, %s total rows.", len(tables), f"{total_rows:,}")
    return tables
