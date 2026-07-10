"""
ERIP Analytics Pipeline Orchestrator
====================================
End-to-end analytics run: load -> validate -> feature-engineer -> analyse ->
persist. Produces two artefacts consumed by the dashboard and the written
insight report:

    reports/analytics_summary.json   # all KPIs, segments, cohorts, forecasts
    data/processed/customer_features.parquet  # RFM base table for ML/BI

Usage:
    python scripts/run_analytics.py               # full dataset
    python scripts/run_analytics.py --sample      # fast run on the sample profile
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd

from erip.analytics import (
    build_customer_features,
    build_monthly_revenue,
    compute_all,
    load_star_schema,
    run_quality_checks,
)
from erip.config.settings import DATA_PROCESSED_DIR, REPORTS_DIR
from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="analytics.log")


def _json_default(obj):
    """Serialise numpy / pandas scalars that json can't handle natively."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    raise TypeError(f"Not JSON serialisable: {type(obj)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ERIP analytics pipeline.")
    parser.add_argument("--sample", action="store_true", help="Use the small sample dataset.")
    args = parser.parse_args()

    t0 = time.time()
    logger.info("=" * 70)
    logger.info("ERIP ANALYTICS PIPELINE START")
    logger.info("=" * 70)

    tables = load_star_schema(sample=args.sample)

    # 1. Data quality gate ---------------------------------------------------
    quality = run_quality_checks(tables)

    # 2. Feature engineering -------------------------------------------------
    customer_features = build_customer_features(tables["dim_customers"], tables["fact_orders"])
    monthly = build_monthly_revenue(tables["fact_orders"])

    # 3. Analytics -----------------------------------------------------------
    metrics = compute_all(tables, customer_features, monthly)
    metrics["data_quality"] = quality
    metrics["meta"] = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "profile": "sample" if args.sample else "full",
        "tables_loaded": len(tables),
        "rows_scanned": int(sum(len(t) for t in tables.values())),
    }

    # 4. Persist -------------------------------------------------------------
    out_json = Path(REPORTS_DIR) / "analytics_summary.json"
    with open(out_json, "w") as fh:
        json.dump(metrics, fh, indent=2, default=_json_default)
    logger.info("Wrote %s", out_json)

    feat_path = Path(DATA_PROCESSED_DIR) / "customer_features.parquet"
    try:
        customer_features.to_parquet(feat_path, index=False)
        logger.info("Wrote %s", feat_path)
    except Exception:  # pyarrow not installed -> fall back to compressed CSV
        feat_path = feat_path.with_suffix(".csv.gz")
        customer_features.to_csv(feat_path, index=False, compression="gzip")
        logger.info("Wrote %s (CSV fallback; install pyarrow for Parquet)", feat_path)

    kpis = metrics["executive_kpis"]
    logger.info("-" * 70)
    logger.info("HEADLINE RESULTS")
    logger.info("  Revenue           : $%s", f"{kpis['total_revenue']:,.0f}")
    logger.info("  Gross profit      : $%s (%.1f%% margin)", f"{kpis['gross_profit']:,.0f}", kpis["gross_margin_pct"])
    logger.info("  Orders / Customers: %s / %s", f"{kpis['total_orders']:,}", f"{kpis['unique_customers']:,}")
    logger.info("  AOV               : $%s", f"{kpis['avg_order_value']:,.2f}")
    logger.info("  Data-quality score: %.2f/100", quality["score"])
    logger.info("Pipeline finished in %.1fs", time.time() - t0)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
