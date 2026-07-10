"""
Product dimension generator.
Produces a product master table across a full retail taxonomy with
realistic pricing, cost (for margin analysis), and lifecycle attributes.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import PRODUCT_TAXONOMY
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_products(n: int = None, seed: int = None) -> pd.DataFrame:
    """
    Generate the product dimension table.

    Args:
        n: number of products (defaults to SCALE.n_products)
        seed: RNG seed

    Returns:
        DataFrame with one row per product (SKU).
    """
    n = n or SCALE.n_products
    rng = np.random.default_rng((seed or SCALE.random_seed) + 1)
    logger.info(f"Generating {n:,} products...")

    categories = list(PRODUCT_TAXONOMY.keys())
    cat_choices = rng.choice(categories, size=n)

    subcats, brands, prices, costs = [], [], [], []
    for cat in cat_choices:
        meta = PRODUCT_TAXONOMY[cat]
        subcats.append(rng.choice(meta["subcategories"]))
        brands.append(rng.choice(meta["brands"]))
        lo, hi = meta["price_range"]
        # log-uniform-ish distribution within range for realistic price skew
        price = float(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi))), 2))
        prices.append(price)
        margin_pct = rng.uniform(0.25, 0.55)  # cost is 45-75% of price
        costs.append(round(price * (1 - margin_pct), 2))

    launch_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days, size=n)
    launch_dates = pd.to_datetime(SCALE.start_date) + pd.to_timedelta(launch_days_ago, unit="D")

    is_discontinued = rng.choice([True, False], size=n, p=[0.08, 0.92])
    weight_kg = np.round(rng.exponential(1.2, size=n).clip(0.05, 40), 2)

    df = pd.DataFrame({
        "product_id": [f"PROD{idx:08d}" for idx in range(1, n + 1)],
        "product_name": [f"{b} {s} {idx}" for idx, (b, s) in enumerate(zip(brands, subcats))],
        "category": cat_choices,
        "subcategory": subcats,
        "brand": brands,
        "unit_price": prices,
        "unit_cost": costs,
        "weight_kg": weight_kg,
        "launch_date": launch_dates,
        "is_discontinued": is_discontinued,
        "rating_avg": np.round(rng.normal(4.0, 0.6, size=n).clip(1, 5), 1),
        "supplier_id": rng.integers(1, SCALE.n_suppliers + 1, size=n),
    })
    df["margin_pct"] = np.round((df["unit_price"] - df["unit_cost"]) / df["unit_price"] * 100, 2)

    logger.info(f"Product generation complete: {len(df):,} rows across {len(categories)} categories")
    return df
