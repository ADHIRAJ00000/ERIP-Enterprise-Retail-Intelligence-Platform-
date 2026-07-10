"""
ERIP Configuration Module
==========================
Centralized configuration for the Enterprise Retail Intelligence Platform.
All scale parameters, paths, and constants are defined here so the entire
pipeline can be resized (e.g. for local dev vs full enterprise scale) by
editing a single file.

Author: ERIP Data Engineering Team
"""

from dataclasses import dataclass, field
from pathlib import Path
from datetime import date


# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATA_SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
MODELS_DIR = PROJECT_ROOT / "models" / "trained"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"

for _dir in (DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_SAMPLE_DIR, MODELS_DIR, REPORTS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ScaleConfig:
    """
    Controls the volume of synthetic data generated.

    Default profile = "portfolio" scale: large enough to be a credible
    enterprise dataset and to stress real ETL / SQL / ML workflows, small
    enough to generate and process on a laptop in minutes rather than hours.

    Every count can be scaled up toward the full enterprise spec
    (5M transactions / 500K customers / 50K products / 300 stores)
    simply by changing the multipliers below.
    """
    n_customers: int = 60_000
    n_products: int = 6_000
    n_stores: int = 120
    n_employees: int = 2_500
    n_suppliers: int = 350
    n_orders: int = 500_000          # ~1 order line generates 1-3 order_items
    n_marketing_campaigns: int = 180
    n_reviews: int = 150_000
    n_website_traffic_days: int = 5 * 365  # 5 years daily traffic per country
    n_coupons: int = 4_000

    start_date: date = date(2021, 1, 1)
    end_date: date = date(2025, 12, 31)

    countries: tuple = (
        "United States", "United Kingdom", "Germany", "France", "India",
        "Canada", "Australia", "Brazil", "Japan", "United Arab Emirates",
    )

    random_seed: int = 42


SCALE = ScaleConfig()


@dataclass(frozen=True)
class DBConfig:
    """PostgreSQL connection configuration (overridden via environment variables in production)."""
    host: str = "localhost"
    port: int = 5433
    database: str = "erip_dw"
    user: str = "erip_user"
    password: str = "changeme"  # pragma: allowlist secret - replaced by env var ERIP_DB_PASSWORD in prod

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


DB = DBConfig()

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_LEVEL = "INFO"
