"""
ERIP Churn Model Training Orchestrator
======================================
Builds a leakage-free churn dataset, trains and selects the best model,
evaluates it on a held-out test set, scores the full customer base, and
persists three artefacts:

    models/trained/churn_model.joblib          # fitted sklearn pipeline
    reports/churn_model.json                   # metrics, lift, importances (dashboard feed)
    data/processed/churn_scores.csv.gz         # per-customer churn probability & risk tier

Usage:
    python scripts/train_churn_model.py
    python scripts/train_churn_model.py --observation-date 2025-03-31 --horizon 275
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib

from erip.analytics import load_star_schema
from erip.ml import build_churn_dataset, score_customer_base, train_churn_model
from erip.config.settings import DATA_PROCESSED_DIR, MODELS_DIR, REPORTS_DIR
from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="ml.log")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the ERIP churn model.")
    parser.add_argument("--observation-date", default="2025-06-30")
    parser.add_argument("--horizon", type=int, default=183, help="Forward window (days) for the churn label.")
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()

    t0 = time.time()
    logger.info("=" * 70)
    logger.info("ERIP CHURN MODEL TRAINING")
    logger.info("=" * 70)

    tables = load_star_schema(sample=args.sample)
    ds = build_churn_dataset(tables, observation_date=args.observation_date, horizon_days=args.horizon)
    result = train_churn_model(ds)

    # Persist the fitted pipeline ------------------------------------------
    model_path = Path(MODELS_DIR) / "churn_model.joblib"
    joblib.dump(result["pipeline"], model_path)
    logger.info("Saved model -> %s", model_path)

    # Score the full base ---------------------------------------------------
    scores = score_customer_base(result["pipeline"], ds)
    scores_path = Path(DATA_PROCESSED_DIR) / "churn_scores.csv.gz"
    scores.to_csv(scores_path, index=False, compression="gzip")
    logger.info("Saved %s churn scores -> %s", f"{len(scores):,}", scores_path)

    tier_counts = scores["risk_tier"].value_counts().reindex(
        ["Critical", "High", "Medium", "Low"]).fillna(0).astype(int)

    # Revenue at risk: monetary of customers predicted High/Critical --------
    at_risk = scores[scores["risk_tier"].isin(["High", "Critical"])]
    revenue_at_risk = float(at_risk["monetary"].sum())

    # Report JSON (drops the un-serialisable pipeline) ----------------------
    report = {k: v for k, v in result.items() if k != "pipeline"}
    report["observation_date"] = args.observation_date
    report["horizon_days"] = args.horizon
    report["n_customers_scored"] = int(len(scores))
    report["risk_tiers"] = tier_counts.to_dict()
    report["revenue_at_risk"] = round(revenue_at_risk, 2)
    report_path = Path(REPORTS_DIR) / "churn_model.json"
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=2)
    logger.info("Saved report -> %s", report_path)

    m = result["metrics"]
    logger.info("-" * 70)
    logger.info("RESULTS")
    logger.info("  Best model      : %s", result["model_name"])
    logger.info("  ROC-AUC         : %.3f   (0.5 = random, 1.0 = perfect)", m["roc_auc"])
    logger.info("  PR-AUC          : %.3f   (baseline %.3f)", m["pr_auc"], m["baseline_churn_rate"])
    logger.info("  Precision/Recall: %.3f / %.3f", m["precision"], m["recall"])
    logger.info("  Top-decile lift : %.2fx", result["decile_lift"][0]["lift"])
    logger.info("  High/Critical   : %s customers · $%s revenue at risk",
                f"{len(at_risk):,}", f"{revenue_at_risk:,.0f}")
    logger.info("  Top driver      : %s", result["feature_importance"][0]["feature"])
    logger.info("Finished in %.1fs", time.time() - t0)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
