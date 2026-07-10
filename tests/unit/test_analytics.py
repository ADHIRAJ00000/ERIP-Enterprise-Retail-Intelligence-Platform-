"""
Unit tests for the ERIP analytics engine.
=========================================
Runs against the fast `sample` data profile so the whole suite completes in
seconds. Validates the three things most likely to silently break an analytics
pipeline: data-quality gating, feature-engineering correctness, and metric
internal consistency.

    pytest -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest

from erip.analytics import (
    build_customer_features,
    build_monthly_revenue,
    compute_all,
    load_star_schema,
    run_quality_checks,
)
from erip.analytics.features import revenue_orders


@pytest.fixture(scope="module")
def tables():
    return load_star_schema(sample=True)


@pytest.fixture(scope="module")
def features(tables):
    return build_customer_features(tables["dim_customers"], tables["fact_orders"])


# --- data quality -----------------------------------------------------------
def test_quality_gate_passes(tables):
    report = run_quality_checks(tables)
    assert report["score"] >= 95, "sample data should pass the quality gate"
    assert report["checks_total"] > 0


def test_referential_integrity_has_no_orphans(tables):
    report = run_quality_checks(tables)
    ri = [c for c in report["checks"] if c["family"] == "referential_integrity"]
    assert ri, "expected referential-integrity checks to run"
    assert all(c["passed"] for c in ri), "no fact row should reference a missing dimension"


# --- feature engineering ----------------------------------------------------
def test_rfm_scores_bounded(features):
    buyers = features[features["frequency"] > 0]
    for col in ("R", "F", "M"):
        assert buyers[col].between(1, 5).all(), f"{col} score must be in 1..5 for buyers"
    assert features["rfm_score"].max() <= 15


def test_every_customer_has_a_segment(features):
    assert features["rfm_segment"].notna().all()
    assert features["rfm_segment"].nunique() >= 3


def test_monetary_reconciles_to_orders(tables, features):
    rev = revenue_orders(tables["fact_orders"])
    assert features["monetary"].sum() == pytest.approx(rev["total_amount"].sum(), rel=1e-6)


# --- metrics ----------------------------------------------------------------
def test_metrics_are_internally_consistent(tables, features):
    monthly = build_monthly_revenue(tables["fact_orders"])
    metrics = compute_all(tables, features, monthly)
    k = metrics["executive_kpis"]

    assert k["total_revenue"] > 0
    assert 0 < k["gross_margin_pct"] < 100
    # gross margin must equal profit / revenue
    implied = 100 * k["gross_profit"] / k["total_revenue"]
    assert k["gross_margin_pct"] == pytest.approx(implied, rel=1e-6)

    # category revenue shares must sum to ~100%
    shares = sum(c["revenue_share_pct"] for c in metrics["category_performance"])
    assert shares == pytest.approx(100, abs=0.5)

    # ABC classes must partition the catalog
    abc_products = sum(a["products"] for a in metrics["product_abc"]["abc_summary"])
    assert abc_products == metrics["product_abc"]["n_products_sold"]
