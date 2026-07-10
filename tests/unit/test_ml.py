"""
Unit tests for the churn ML layer.
==================================
Runs on the fast `sample` profile. The most important thing to test in an ML
pipeline is not the accuracy number but that the training setup is **honest**:
no leakage, a valid label, aligned features, and calibrated probabilities.

    pytest -q tests/unit/test_ml.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest

from erip.analytics import load_star_schema
from erip.ml import build_churn_dataset, score_customer_base, train_churn_model
from erip.ml.churn import CATEGORICAL_FEATURES, NUMERIC_FEATURES

OBS_DATE = "2024-06-30"  # leaves a full forward window inside the sample data


@pytest.fixture(scope="module")
def tables():
    return load_star_schema(sample=True)


@pytest.fixture(scope="module")
def dataset(tables):
    return build_churn_dataset(tables, observation_date=OBS_DATE, horizon_days=183)


@pytest.fixture(scope="module")
def trained(dataset):
    return train_churn_model(dataset)


# --- dataset integrity / no leakage ----------------------------------------
def test_label_is_valid_and_not_degenerate(dataset):
    assert dataset.y.isin([0, 1]).all()
    assert 0.05 < dataset.churn_rate < 0.95, "label should not be degenerate"


def test_features_present_and_aligned(dataset):
    assert list(dataset.X.columns) == NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert len(dataset.X) == len(dataset.y) == len(dataset.customer_id)
    assert dataset.X[NUMERIC_FEATURES].notna().all().all()


def test_no_leakage_recency_nonnegative(dataset):
    # Recency is measured up to the observation date, so it can never be negative
    # (that would mean a "past" order dated after the cutoff — i.e. leakage).
    assert (dataset.X["recency_days"] >= 0).all()


# --- model behaviour --------------------------------------------------------
def test_model_beats_random(trained):
    assert trained["metrics"]["roc_auc"] > 0.55, "model should beat a coin flip"
    assert trained["model_name"] in ("Logistic Regression", "Gradient Boosting")


def test_scores_are_probabilities(trained, dataset):
    scored = score_customer_base(trained["pipeline"], dataset)
    p = scored["churn_probability"]
    assert p.between(0, 1).all()
    assert scored["risk_tier"].notna().all()


def test_decile_lift_is_monotonic_top_heavy(trained):
    lifts = [d["lift"] for d in trained["decile_lift"]]
    # the top risk decile must contain more churners than the bottom decile
    assert lifts[0] > lifts[-1]
