"""
Customer dimension generator.
Produces a realistic customer master table with demographics, geography,
acquisition channel, and a derived (but pre-seeded) loyalty tier.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import (
    FIRST_NAMES, LAST_NAMES, COUNTRY_DATA, MARKETING_CHANNELS, CUSTOMER_SEGMENTS,
)
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_customers(n: int = None, seed: int = None) -> pd.DataFrame:
    """
    Generate the customer dimension table.

    Args:
        n: number of customers (defaults to SCALE.n_customers)
        seed: RNG seed (defaults to SCALE.random_seed)

    Returns:
        DataFrame with one row per customer.
    """
    n = n or SCALE.n_customers
    rng = np.random.default_rng(seed or SCALE.random_seed)
    logger.info(f"Generating {n:,} customers...")

    countries = list(COUNTRY_DATA.keys())
    # Weighted toward larger markets (US, India, UK, Germany) - realistic skew
    country_weights = np.array([0.28, 0.13, 0.11, 0.10, 0.14, 0.08, 0.06, 0.05, 0.03, 0.02])
    country_weights = country_weights / country_weights.sum()

    customer_countries = rng.choice(countries, size=n, p=country_weights)
    first_names = rng.choice(FIRST_NAMES, size=n)
    last_names = rng.choice(LAST_NAMES, size=n)

    cities = np.array([
        rng.choice(COUNTRY_DATA[c]["cities"]) for c in customer_countries
    ])

    signup_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days, size=n)
    signup_dates = pd.to_datetime(SCALE.start_date) + pd.to_timedelta(signup_days_ago, unit="D")

    ages = rng.normal(loc=38, scale=13, size=n).clip(18, 85).astype(int)
    genders = rng.choice(["Female", "Male", "Other"], size=n, p=[0.49, 0.48, 0.03])

    # Tenure-based segment assignment (rough heuristic, refined later by RFM)
    tenure_days = (pd.Timestamp(SCALE.end_date) - signup_dates).days
    segment_probs_by_tenure = np.where(
        tenure_days < 90, 0, np.where(tenure_days < 365, 1, np.where(tenure_days < 730, 2, 3))
    )
    base_segments = np.array(CUSTOMER_SEGMENTS)
    segments = base_segments[np.clip(segment_probs_by_tenure + rng.integers(-1, 2, size=n), 0, len(base_segments) - 1)]

    df = pd.DataFrame({
        "customer_id": [f"CUST{idx:08d}" for idx in range(1, n + 1)],
        "first_name": first_names,
        "last_name": last_names,
        "email": [
            f"{fn.lower()}.{ln.lower()}{idx}@example.com"
            for idx, (fn, ln) in enumerate(zip(first_names, last_names))
        ],
        "gender": genders,
        "age": ages,
        "country": customer_countries,
        "city": cities,
        "currency": [COUNTRY_DATA[c]["currency"] for c in customer_countries],
        "signup_date": signup_dates,
        "acquisition_channel": rng.choice(MARKETING_CHANNELS, size=n),
        "customer_segment": segments,
        "is_loyalty_member": rng.choice([True, False], size=n, p=[0.42, 0.58]),
        "marketing_opt_in": rng.choice([True, False], size=n, p=[0.65, 0.35]),
    })

    logger.info(f"Customer generation complete: {len(df):,} rows, {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
    return df
