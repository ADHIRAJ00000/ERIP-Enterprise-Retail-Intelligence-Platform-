"""ERIP analytics engine: loading, quality, feature engineering and metrics."""

from erip.analytics.loader import load_star_schema, load_table
from erip.analytics.quality import run_quality_checks
from erip.analytics.features import build_customer_features, build_monthly_revenue
from erip.analytics.metrics import compute_all

__all__ = [
    "load_star_schema",
    "load_table",
    "run_quality_checks",
    "build_customer_features",
    "build_monthly_revenue",
    "compute_all",
]
