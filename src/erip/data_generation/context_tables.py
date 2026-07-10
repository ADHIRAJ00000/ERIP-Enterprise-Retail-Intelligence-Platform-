"""
Supporting context tables: website traffic, weather, holiday calendar,
economic indicators. These enrich the fact tables for richer EDA
(e.g. "does rainy weather suppress in-store traffic?",
"do holidays correlate with order volume spikes?").
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import COUNTRY_DATA, WEATHER_CONDITIONS, US_HOLIDAYS
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_website_traffic(seed: int = None) -> pd.DataFrame:
    """Generate daily website traffic per country for the full date range."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 13)
    date_range = pd.date_range(SCALE.start_date, SCALE.end_date, freq="D")
    countries = list(COUNTRY_DATA.keys())
    logger.info(f"Generating website traffic: {len(date_range):,} days x {len(countries)} countries...")

    rows = []
    for country in countries:
        base_visitors = rng.integers(5000, 80000)
        dow_lift = np.where(np.isin(date_range.dayofweek, [4, 5]), 1.25, 1.0)
        month_lift = np.where(np.isin(date_range.month, [11, 12]), 1.5, 1.0)
        trend = np.linspace(1.0, 1.35, len(date_range))  # gradual growth
        visitors = (base_visitors * dow_lift * month_lift * trend * rng.normal(1, 0.08, len(date_range))).clip(min=100).astype(int)

        sessions = (visitors * rng.uniform(1.1, 1.4, len(date_range))).astype(int)
        bounce_rate = np.round(rng.uniform(0.25, 0.55, len(date_range)), 3)
        conversion_rate = np.round(rng.uniform(0.015, 0.06, len(date_range)), 4)

        rows.append(pd.DataFrame({
            "date": date_range,
            "country": country,
            "visitors": visitors,
            "sessions": sessions,
            "bounce_rate": bounce_rate,
            "conversion_rate": conversion_rate,
            "avg_session_duration_sec": rng.integers(45, 420, len(date_range)),
        }))

    df = pd.concat(rows, ignore_index=True)
    logger.info(f"Website traffic generation complete: {len(df):,} rows")
    return df


def generate_weather(stores_df: pd.DataFrame, seed: int = None) -> pd.DataFrame:
    """Generate daily weather observations per unique store city."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 14)
    date_range = pd.date_range(SCALE.start_date, SCALE.end_date, freq="D")
    unique_cities = stores_df[["country", "city"]].drop_duplicates()
    logger.info(f"Generating weather: {len(date_range):,} days x {len(unique_cities)} cities...")

    rows = []
    for _, row in unique_cities.iterrows():
        # seasonal sinusoidal temperature curve + noise
        day_of_year = date_range.dayofyear.values
        seasonal_temp = 15 + 12 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        temp_c = np.round(seasonal_temp + rng.normal(0, 4, len(date_range)), 1)
        condition = rng.choice(WEATHER_CONDITIONS, size=len(date_range),
                                p=[0.35, 0.18, 0.22, 0.06, 0.07, 0.07, 0.05])
        rows.append(pd.DataFrame({
            "date": date_range,
            "country": row["country"],
            "city": row["city"],
            "temperature_c": temp_c,
            "condition": condition,
            "precipitation_mm": np.round(rng.exponential(2, len(date_range)) *
                                          np.isin(condition, ["Rainy", "Stormy", "Snowy"]), 1),
        }))

    df = pd.concat(rows, ignore_index=True)
    logger.info(f"Weather generation complete: {len(df):,} rows")
    return df


def generate_holiday_calendar() -> pd.DataFrame:
    """Generate a holiday calendar table spanning all years in the date range."""
    logger.info("Generating holiday calendar...")
    years = range(SCALE.start_date.year, SCALE.end_date.year + 1)
    rows = []
    for year in years:
        for name, md in US_HOLIDAYS:
            date = pd.Timestamp(f"{year}-{md}")
            rows.append({"date": date, "holiday_name": name, "is_major_shopping_event": name in
                         ("Black Friday", "Cyber Monday", "Christmas", "Thanksgiving")})
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    logger.info(f"Holiday calendar generation complete: {len(df):,} rows")
    return df


def generate_economic_indicators(seed: int = None) -> pd.DataFrame:
    """Generate monthly economic indicators per country (inflation, unemployment, consumer confidence)."""
    rng = np.random.default_rng((seed or SCALE.random_seed) + 15)
    months = pd.date_range(SCALE.start_date, SCALE.end_date, freq="MS")
    countries = list(COUNTRY_DATA.keys())
    logger.info(f"Generating economic indicators: {len(months):,} months x {len(countries)} countries...")

    rows = []
    for country in countries:
        base_inflation = rng.uniform(1.5, 6.0)
        base_unemployment = rng.uniform(3.0, 9.0)
        inflation = (base_inflation + rng.normal(0, 0.4, len(months))).clip(0, 15).round(2)
        unemployment = (base_unemployment + rng.normal(0, 0.3, len(months))).clip(1, 20).round(2)
        consumer_confidence = (100 + rng.normal(0, 8, len(months))).clip(40, 160).round(1)
        rows.append(pd.DataFrame({
            "month": months,
            "country": country,
            "inflation_rate_pct": inflation,
            "unemployment_rate_pct": unemployment,
            "consumer_confidence_index": consumer_confidence,
            "gdp_growth_pct": np.round(rng.normal(2.2, 1.5, len(months)), 2),
        }))

    df = pd.concat(rows, ignore_index=True)
    logger.info(f"Economic indicators generation complete: {len(df):,} rows")
    return df
