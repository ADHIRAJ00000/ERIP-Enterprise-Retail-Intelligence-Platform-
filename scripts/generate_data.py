"""
ERIP Data Generation Orchestrator
==================================
Runs the full synthetic data generation pipeline end-to-end and writes
every table to /data/raw as Parquet (efficient) and a CSV sample for
quick inspection in Excel/Power BI/Tableau.

Usage:
    python scripts/generate_data.py
    python scripts/generate_data.py --sample-only   # tiny dataset for fast local testing
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from erip.config.settings import SCALE, DATA_RAW_DIR, DATA_SAMPLE_DIR
from erip.utils.logger import get_logger
from erip.data_generation.customers import generate_customers
from erip.data_generation.products import generate_products
from erip.data_generation.stores_employees_suppliers import (
    generate_stores, generate_employees, generate_suppliers,
)
from erip.data_generation.transactions import (
    generate_orders_and_items, generate_payments, generate_returns, generate_shipping,
)
from erip.data_generation.marketing_reviews import generate_marketing_campaigns, generate_reviews
from erip.data_generation.inventory_coupons import generate_inventory, generate_coupons
from erip.data_generation.context_tables import (
    generate_website_traffic, generate_weather, generate_holiday_calendar, generate_economic_indicators,
)

logger = get_logger(__name__, log_file="data_generation.log")


def save(df: pd.DataFrame, name: str, out_dir: Path):
    """
    Save as gzip-compressed CSV. (Parquet is preferred in production for
    columnar performance - swap to df.to_parquet() if pyarrow/fastparquet
    is available in your environment; CSV is used here for zero-dependency
    portability into Power BI / Tableau / Excel.)
    """
    path = out_dir / f"{name}.csv.gz"
    df.to_csv(path, index=False, compression="gzip")
    logger.info(f"  -> saved {name}: {len(df):,} rows -> {path}")


def run(sample_only: bool = False):
    t0 = time.time()
    out_dir = DATA_SAMPLE_DIR if sample_only else DATA_RAW_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    overrides = {}
    if sample_only:
        overrides = dict(n_customers=2000, n_products=300, n_stores=15, n_employees=120,
                          n_suppliers=30, n_orders=8000, n_marketing_campaigns=20, n_reviews=3000)

    logger.info("=" * 70)
    logger.info(f"ERIP DATA GENERATION PIPELINE — {'SAMPLE' if sample_only else 'FULL'} MODE")
    logger.info("=" * 70)

    # ---- Dimensions ----
    customers = generate_customers(n=overrides.get("n_customers"))
    save(customers, "dim_customers", out_dir)

    products = generate_products(n=overrides.get("n_products"))
    save(products, "dim_products", out_dir)

    stores = generate_stores(n=overrides.get("n_stores"))
    save(stores, "dim_stores", out_dir)

    employees = generate_employees(stores, n=overrides.get("n_employees"))
    save(employees, "dim_employees", out_dir)

    suppliers = generate_suppliers(n=overrides.get("n_suppliers"))
    save(suppliers, "dim_suppliers", out_dir)

    # ---- Facts: transactions ----
    orders, order_items = generate_orders_and_items(
        customers, products, stores, n_orders=overrides.get("n_orders")
    )
    save(orders, "fact_orders", out_dir)
    save(order_items, "fact_order_items", out_dir)

    payments = generate_payments(orders)
    save(payments, "fact_payments", out_dir)

    returns = generate_returns(orders, order_items)
    save(returns, "fact_returns", out_dir)

    shipping = generate_shipping(orders)
    save(shipping, "fact_shipping", out_dir)

    # ---- Facts: marketing & engagement ----
    campaigns = generate_marketing_campaigns(n=overrides.get("n_marketing_campaigns"))
    save(campaigns, "fact_marketing_campaigns", out_dir)

    reviews = generate_reviews(order_items, customers, n=overrides.get("n_reviews"))
    save(reviews, "fact_reviews", out_dir)

    coupons = generate_coupons()
    save(coupons, "dim_coupons", out_dir)

    inventory = generate_inventory(products, stores)
    save(inventory, "fact_inventory", out_dir)

    # ---- Context tables ----
    if not sample_only:
        traffic = generate_website_traffic()
        save(traffic, "fact_website_traffic", out_dir)

        weather = generate_weather(stores)
        save(weather, "fact_weather", out_dir)

    holidays = generate_holiday_calendar()
    save(holidays, "dim_holiday_calendar", out_dir)

    econ = generate_economic_indicators()
    save(econ, "fact_economic_indicators", out_dir)

    elapsed = time.time() - t0
    logger.info("=" * 70)
    logger.info(f"PIPELINE COMPLETE in {elapsed:.1f}s. Output: {out_dir}")
    logger.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ERIP synthetic retail dataset")
    parser.add_argument("--sample-only", action="store_true", help="Generate a tiny dataset for fast local testing")
    args = parser.parse_args()
    run(sample_only=args.sample_only)
