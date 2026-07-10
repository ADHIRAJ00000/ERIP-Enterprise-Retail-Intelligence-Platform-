"""
Store, Employee, and Supplier dimension generators.
"""

import numpy as np
import pandas as pd

from erip.config.settings import SCALE
from erip.data_generation.reference_data import (
    COUNTRY_DATA, STORE_TYPES, FIRST_NAMES, LAST_NAMES, EMPLOYEE_ROLES,
)
from erip.utils.logger import get_logger

logger = get_logger(__name__)


def generate_stores(n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate the store dimension table, distributed across all 10 countries."""
    n = n or SCALE.n_stores
    rng = np.random.default_rng((seed or SCALE.random_seed) + 2)
    logger.info(f"Generating {n:,} stores...")

    countries = list(COUNTRY_DATA.keys())
    store_countries = rng.choice(countries, size=n)
    cities = np.array([rng.choice(COUNTRY_DATA[c]["cities"]) for c in store_countries])

    opened_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days, size=n)
    opened_dates = pd.to_datetime(SCALE.start_date) - pd.to_timedelta(0, unit="D") + pd.to_timedelta(opened_days_ago, unit="D")

    df = pd.DataFrame({
        "store_id": [f"ST{idx:05d}" for idx in range(1, n + 1)],
        "store_name": [f"{c} {t}" for c, t in zip(cities, rng.choice(STORE_TYPES, size=n))],
        "store_type": rng.choice(STORE_TYPES, size=n),
        "country": store_countries,
        "city": cities,
        "square_footage": rng.integers(800, 45000, size=n),
        "opened_date": opened_dates,
        "is_active": rng.choice([True, False], size=n, p=[0.94, 0.06]),
        "manager_employee_id": None,  # back-filled after employees are generated
    })
    logger.info(f"Store generation complete: {len(df):,} rows")
    return df


def generate_employees(stores_df: pd.DataFrame, n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate the employee dimension table, each employee tied to a store."""
    n = n or SCALE.n_employees
    rng = np.random.default_rng((seed or SCALE.random_seed) + 3)
    logger.info(f"Generating {n:,} employees...")

    store_ids = rng.choice(stores_df["store_id"], size=n)
    hire_days_ago = rng.integers(0, (SCALE.end_date - SCALE.start_date).days, size=n)
    hire_dates = pd.to_datetime(SCALE.start_date) + pd.to_timedelta(hire_days_ago, unit="D")

    df = pd.DataFrame({
        "employee_id": [f"EMP{idx:07d}" for idx in range(1, n + 1)],
        "first_name": rng.choice(FIRST_NAMES, size=n),
        "last_name": rng.choice(LAST_NAMES, size=n),
        "role": rng.choice(EMPLOYEE_ROLES, size=n,
                            p=[0.05, 0.07, 0.30, 0.18, 0.08, 0.12, 0.02, 0.06, 0.04, 0.08]),
        "store_id": store_ids,
        "hire_date": hire_dates,
        "annual_salary_usd": np.round(rng.normal(48000, 18000, size=n).clip(22000, 180000), -2),
        "performance_rating": np.round(rng.normal(3.6, 0.7, size=n).clip(1, 5), 1),
        "is_active": rng.choice([True, False], size=n, p=[0.88, 0.12]),
    })
    logger.info(f"Employee generation complete: {len(df):,} rows")
    return df


def generate_suppliers(n: int = None, seed: int = None) -> pd.DataFrame:
    """Generate the supplier dimension table."""
    n = n or SCALE.n_suppliers
    rng = np.random.default_rng((seed or SCALE.random_seed) + 4)
    logger.info(f"Generating {n:,} suppliers...")

    countries = list(COUNTRY_DATA.keys())
    supplier_countries = rng.choice(countries, size=n)
    supplier_name_roots = ["Global", "Prime", "United", "Apex", "Summit", "Atlas", "Pioneer", "Vertex", "Crown", "Nexus"]
    supplier_name_suffix = ["Supply Co.", "Distribution", "Industries", "Goods Ltd.", "Trading", "Logistics"]

    df = pd.DataFrame({
        "supplier_id": list(range(1, n + 1)),
        "supplier_name": [
            f"{rng.choice(supplier_name_roots)} {rng.choice(supplier_name_suffix)}" for _ in range(n)
        ],
        "country": supplier_countries,
        "reliability_score": np.round(rng.normal(85, 10, size=n).clip(40, 100), 1),
        "avg_lead_time_days": rng.integers(2, 45, size=n),
        "contract_start_date": pd.to_datetime(SCALE.start_date) +
            pd.to_timedelta(rng.integers(0, 365, size=n), unit="D"),
        "is_active": rng.choice([True, False], size=n, p=[0.91, 0.09]),
    })
    logger.info(f"Supplier generation complete: {len(df):,} rows")
    return df
