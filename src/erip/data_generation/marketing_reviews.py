"""
Marketing campaigns and product reviews generators.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import MARKETING_CHANNELS, CAMPAIGN_TYPES, COUNTRY_DATA
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_marketing_campaigns(n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate the marketing campaigns dimension/fact table with spend & performance metrics."""
    n = n or SCALE.n_marketing_campaigns
    rng = np.random.default_rng((seed or SCALE.random_seed) + 9)
    logger.info(f"Generating {n:,} marketing campaigns...")

    start_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days - 30, size=n)
    start_dates = pd.to_datetime(SCALE.start_date) + pd.to_timedelta(start_days_ago, unit="D")
    durations = rng.integers(3, 30, size=n)
    end_dates = start_dates + pd.to_timedelta(durations, unit="D")

    spend = np.round(rng.exponential(15000, size=n).clip(500, 250000), 2)
    impressions = (spend * rng.uniform(20, 80, size=n)).astype(int)
    ctr = rng.uniform(0.005, 0.08, size=n)
    clicks = (impressions * ctr).astype(int)
    conv_rate = rng.uniform(0.01, 0.12, size=n)
    conversions = (clicks * conv_rate).astype(int)
    revenue_generated = np.round(conversions * rng.uniform(30, 200, size=n), 2)

    df = pd.DataFrame({
        "campaign_id": [f"CMP{idx:05d}" for idx in range(1, n + 1)],
        "campaign_name": [f"{rng.choice(CAMPAIGN_TYPES)} - {y}" for y in start_dates.year],
        "campaign_type": rng.choice(CAMPAIGN_TYPES, size=n),
        "channel": rng.choice(MARKETING_CHANNELS, size=n),
        "target_country": rng.choice(list(COUNTRY_DATA.keys()), size=n),
        "start_date": start_dates,
        "end_date": end_dates,
        "budget_usd": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "revenue_generated_usd": revenue_generated,
    })
    df["ctr_pct"] = np.round(df["clicks"] / df["impressions"] * 100, 3)
    df["conversion_rate_pct"] = np.round(df["conversions"] / df["clicks"].clip(lower=1) * 100, 3)
    df["roas"] = np.round(df["revenue_generated_usd"] / df["budget_usd"], 2)

    logger.info(f"Marketing campaign generation complete: {len(df):,} rows")
    return df


def generate_reviews(order_items_df: pd.DataFrame, customers_df: pd.DataFrame, n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate product reviews tied to actual purchased order items."""
    n = n or SCALE.n_reviews
    rng = np.random.default_rng((seed or SCALE.random_seed) + 10)
    n = min(n, len(order_items_df))
    logger.info(f"Generating {n:,} product reviews...")

    sampled = order_items_df.sample(n=n, random_state=int(seed or SCALE.random_seed))
    review_delay = rng.integers(1, 45, size=n)
    review_dates = pd.to_datetime(sampled["order_date"].values) + pd.to_timedelta(review_delay, unit="D")

    rating = rng.choice([1, 2, 3, 4, 5], size=n, p=[0.05, 0.07, 0.13, 0.32, 0.43])
    sentiment_map = {1: "Negative", 2: "Negative", 3: "Neutral", 4: "Positive", 5: "Positive"}

    df = pd.DataFrame({
        "review_id": [f"REV{idx:08d}" for idx in range(1, n + 1)],
        "product_id": sampled["product_id"].values,
        "order_id": sampled["order_id"].values,
        "customer_id": rng.choice(customers_df["customer_id"], size=n),
        "review_date": review_dates,
        "rating": rating,
        "sentiment": [sentiment_map[r] for r in rating],
        "verified_purchase": True,
        "helpful_votes": rng.poisson(3, size=n),
    })
    logger.info(f"Review generation complete: {len(df):,} rows, avg rating {df['rating'].mean():.2f}")
    return df
