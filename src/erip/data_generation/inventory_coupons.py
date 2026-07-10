"""
Inventory and coupons generators.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_inventory(products_df: pd.DataFrame, stores_df: pd.DataFrame, seed: int = None) -> pd.DataFrame:
    """
    Generate a snapshot inventory table: each active store carries a random
    subset of the product catalog (~25-60% of SKUs) with stock levels,
    reorder points, and a derived stock-health flag.
    """
    rng = np.random.default_rng((seed or SCALE.random_seed) + 11)
    active_stores = stores_df[stores_df["is_active"]]
    logger.info(f"Generating inventory snapshot for {len(active_stores):,} stores...")

    rows = []
    for store_id in active_stores["store_id"]:
        n_skus = rng.integers(int(len(products_df) * 0.25), int(len(products_df) * 0.60))
        sku_sample = products_df.sample(n=n_skus, random_state=rng.integers(0, 1_000_000))["product_id"].values
        rows.append(pd.DataFrame({
            "store_id": store_id,
            "product_id": sku_sample,
        }))

    inv = pd.concat(rows, ignore_index=True)
    n = len(inv)
    inv["stock_on_hand"] = rng.integers(0, 500, size=n)
    inv["reorder_point"] = rng.integers(10, 80, size=n)
    inv["reorder_quantity"] = rng.integers(50, 400, size=n)
    inv["last_restocked_date"] = pd.to_datetime(SCALE.end_date) - pd.to_timedelta(rng.integers(0, 90, size=n), unit="D")
    inv["stock_status"] = np.select(
        [inv["stock_on_hand"] == 0, inv["stock_on_hand"] < inv["reorder_point"]],
        ["Out of Stock", "Low Stock"],
        default="In Stock",
    )
    logger.info(f"Inventory generation complete: {len(inv):,} rows")
    return inv


def generate_coupons(n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate the coupons/promo-codes dimension table."""
    n = n or SCALE.n_coupons
    rng = np.random.default_rng((seed or SCALE.random_seed) + 12)
    logger.info(f"Generating {n:,} coupons...")

    discount_type = rng.choice(["Percentage", "Fixed Amount", "Free Shipping"], size=n, p=[0.55, 0.30, 0.15])
    discount_value = np.where(
        discount_type == "Percentage", rng.choice([5, 10, 15, 20, 25, 30], size=n),
        np.where(discount_type == "Fixed Amount", rng.choice([5, 10, 15, 25, 50], size=n), 0)
    )
    issue_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days, size=n)
    issue_dates = pd.to_datetime(SCALE.start_date) + pd.to_timedelta(issue_days_ago, unit="D")

    df = pd.DataFrame({
        "coupon_id": [f"CPN{idx:06d}" for idx in range(1, n + 1)],
        "coupon_code": [f"SAVE{rng.integers(1000,9999)}" for _ in range(n)],
        "discount_type": discount_type,
        "discount_value": discount_value,
        "issue_date": issue_dates,
        "expiry_date": issue_dates + pd.to_timedelta(rng.integers(7, 90, size=n), unit="D"),
        "min_purchase_amount": rng.choice([0, 25, 50, 100], size=n),
        "times_redeemed": rng.poisson(35, size=n),
        "is_active": rng.choice([True, False], size=n, p=[0.3, 0.7]),
    })
    logger.info(f"Coupon generation complete: {len(df):,} rows")
    return df
