"""
Customer churn prediction.
==========================
A leakage-free, point-in-time churn model.

Problem framing
---------------
We stand at an **observation date** (default 2025-06-30) and ask: of the
customers who were *active in the prior 12 months*, which ones will make **no
purchase in the next 6 months**? That forward-looking silence is our churn label.

Why this framing matters (and is a strong interview point):

* **No leakage.** Every feature is computed strictly from data *on or before*
  the observation date; the label is computed strictly *after* it. The model
  never sees the future it is trying to predict.
* **Actionable.** A 6-month horizon is long enough to be meaningful and short
  enough that a retention team can still intervene.
* **Balanced.** ~43% of eligible customers churn under this definition, so the
  problem is learnable without heavy resampling.

Pipeline
--------
build_churn_dataset -> train_churn_model (LogReg vs. HistGradientBoosting,
picked by cross-validated ROC-AUC) -> evaluate -> score the full base into
risk tiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from erip.analytics.features import revenue_orders
from erip.utils.logger import get_logger

logger = get_logger(__name__, log_file="ml.log")

NUMERIC_FEATURES = [
    "recency_days", "frequency", "monetary", "avg_order_value",
    "tenure_days", "distinct_categories", "n_returns", "age",
]
CATEGORICAL_FEATURES = [
    "country", "acquisition_channel", "customer_segment", "is_loyalty_member",
]
TARGET = "churned"


@dataclass
class ChurnDataset:
    """Feature matrix + label + the metadata needed to explain the split."""
    X: pd.DataFrame
    y: pd.Series
    customer_id: pd.Series
    observation_date: pd.Timestamp
    horizon_days: int
    churn_rate: float = field(init=False)

    def __post_init__(self):
        self.churn_rate = float(self.y.mean())


def build_churn_dataset(
    tables: dict[str, pd.DataFrame],
    observation_date: str = "2025-06-30",
    horizon_days: int = 183,
    active_window_days: int = 365,
) -> ChurnDataset:
    """
    Construct a point-in-time churn training set.

    Features use only orders/returns on or before `observation_date`; the label
    uses only orders strictly after it, within `horizon_days`.
    """
    obs = pd.Timestamp(observation_date)
    rev = revenue_orders(tables["fact_orders"])
    hist = rev[rev["order_date"] <= obs]
    future = rev[(rev["order_date"] > obs) & (rev["order_date"] <= obs + pd.Timedelta(days=horizon_days))]

    # Behavioural features as of the observation date -----------------------
    agg = hist.groupby("customer_id").agg(
        recency_days=("order_date", lambda s: (obs - s.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("total_amount", "sum"),
        avg_order_value=("total_amount", "mean"),
        first_order=("order_date", "min"),
    )
    agg["tenure_days"] = (obs - agg["first_order"]).dt.days

    # Category breadth (distinct product categories ever purchased) ----------
    items = tables["fact_order_items"][["order_id", "product_id", "order_date"]]
    items = items[items["order_date"] <= obs]
    prod_cat = tables["dim_products"][["product_id", "category"]]
    hist_orders = set(hist["order_id"].unique())
    it = items[items["order_id"].isin(hist_orders)].merge(prod_cat, on="product_id", how="left")
    order_owner = hist[["order_id", "customer_id"]]
    it = it.merge(order_owner, on="order_id", how="left")
    distinct_cat = it.groupby("customer_id")["category"].nunique().rename("distinct_categories")

    # Return behaviour ------------------------------------------------------
    n_returns = pd.Series(0, index=agg.index, name="n_returns", dtype=int)
    if "fact_returns" in tables:
        ret = tables["fact_returns"].merge(order_owner, on="order_id", how="inner")
        ret = ret[ret["return_date"] <= obs] if "return_date" in ret else ret
        rc = ret.groupby("customer_id")["return_id"].count()
        n_returns = rc.reindex(agg.index).fillna(0).astype(int).rename("n_returns")

    # Customer attributes ---------------------------------------------------
    cust = tables["dim_customers"].set_index("customer_id")

    df = agg.join(distinct_cat).join(n_returns)
    df["distinct_categories"] = df["distinct_categories"].fillna(0).astype(int)
    df = df.join(cust[["age", "country", "acquisition_channel", "customer_segment",
                       "is_loyalty_member", "signup_date"]])

    # Eligibility: active in the year before the observation date -----------
    df = df[df["recency_days"] <= active_window_days].copy()

    # Label: churn = no purchase in the forward window ----------------------
    buyers_future = set(future["customer_id"].unique())
    df[TARGET] = (~df.index.isin(buyers_future)).astype(int)

    df["is_loyalty_member"] = df["is_loyalty_member"].astype(str)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    y = df[TARGET].copy()
    logger.info(
        "Churn dataset: %s customers · %d features · churn rate %.1f%% (obs=%s, horizon=%dd)",
        f"{len(X):,}", X.shape[1], 100 * y.mean(), observation_date, horizon_days,
    )
    return ChurnDataset(X=X, y=y, customer_id=pd.Series(df.index), observation_date=obs, horizon_days=horizon_days)


def _build_pipeline(estimator) -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", drop="if_binary"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("pre", pre), ("clf", estimator)])


def train_churn_model(ds: ChurnDataset, random_state: int = 42) -> dict:
    """
    Train and compare two models, select the best by cross-validated ROC-AUC,
    evaluate on a held-out test set, and return everything the report/dashboard
    needs (metrics, ROC curve, decile lift, feature importances, fitted model).
    """
    X_train, X_test, y_train, y_test = train_test_split(
        ds.X, ds.y, test_size=0.25, stratify=ds.y, random_state=random_state
    )

    candidates = {
        "Logistic Regression": _build_pipeline(
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=random_state)
        ),
        "Gradient Boosting": _build_pipeline(
            HistGradientBoostingClassifier(
                max_iter=300, learning_rate=0.08, max_depth=6, random_state=random_state
            )
        ),
    }

    leaderboard = {}
    for name, pipe in candidates.items():
        cv = cross_val_score(pipe, X_train, y_train, cv=5, scoring="roc_auc", n_jobs=-1)
        leaderboard[name] = float(cv.mean())
        logger.info("  %-20s CV ROC-AUC %.4f (+/- %.4f)", name, cv.mean(), cv.std())

    best_name = max(leaderboard, key=leaderboard.get)
    best = candidates[best_name]
    best.fit(X_train, y_train)
    logger.info("Selected model: %s", best_name)

    proba = best.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    fpr, tpr, _ = roc_curve(y_test, proba)
    roc_pts = [{"fpr": round(float(a), 4), "tpr": round(float(b), 4)}
               for a, b in zip(fpr[:: max(1, len(fpr) // 60)], tpr[:: max(1, len(tpr) // 60)])]

    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_test, proba)), 4),
        "precision": round(float(precision_score(y_test, pred)), 4),
        "recall": round(float(recall_score(y_test, pred)), 4),
        "f1": round(float(f1_score(y_test, pred)), 4),
        "baseline_churn_rate": round(float(ds.churn_rate), 4),
    }
    cm = confusion_matrix(y_test, pred)
    metrics["confusion_matrix"] = {
        "tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]), "tp": int(cm[1, 1]),
    }

    lift = _decile_lift(y_test.values, proba)
    importances = _feature_importance(best, X_test, y_test, random_state)

    logger.info("Test ROC-AUC %.3f · PR-AUC %.3f · precision %.3f · recall %.3f",
                metrics["roc_auc"], metrics["pr_auc"], metrics["precision"], metrics["recall"])

    return {
        "model_name": best_name,
        "leaderboard": {k: round(v, 4) for k, v in leaderboard.items()},
        "metrics": metrics,
        "roc_curve": roc_pts,
        "decile_lift": lift,
        "feature_importance": importances,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "pipeline": best,
    }


def _decile_lift(y_true: np.ndarray, proba: np.ndarray) -> list[dict]:
    """Rank customers by predicted risk into deciles; report churn rate & lift per decile."""
    order = np.argsort(-proba)
    y_sorted = y_true[order]
    base = y_true.mean()
    n = len(y_true)
    out = []
    for d in range(10):
        lo, hi = d * n // 10, (d + 1) * n // 10
        seg = y_sorted[lo:hi]
        rate = float(seg.mean()) if len(seg) else 0.0
        out.append({
            "decile": d + 1,
            "churn_rate": round(rate, 4),
            "lift": round(rate / base, 2) if base else 0.0,
        })
    return out


def _feature_importance(pipe: Pipeline, X_test, y_test, random_state: int) -> list[dict]:
    """Permutation importance on the fitted pipeline (model-agnostic, honest)."""
    r = permutation_importance(pipe, X_test, y_test, n_repeats=5,
                               random_state=random_state, scoring="roc_auc", n_jobs=-1)
    feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    imp = sorted(
        [{"feature": f, "importance": round(float(m), 4)} for f, m in zip(feats, r.importances_mean)],
        key=lambda d: d["importance"], reverse=True,
    )
    return imp


def score_customer_base(pipe: Pipeline, ds: ChurnDataset) -> pd.DataFrame:
    """Score every eligible customer into a churn probability and risk tier."""
    proba = pipe.predict_proba(ds.X)[:, 1]
    out = ds.X.copy()
    out.insert(0, "customer_id", ds.customer_id.values)
    out["churn_probability"] = proba.round(4)
    out["actual_churned"] = ds.y.values
    out["risk_tier"] = pd.cut(
        proba, bins=[-0.01, 0.3, 0.6, 0.8, 1.01],
        labels=["Low", "Medium", "High", "Critical"],
    )
    return out.sort_values("churn_probability", ascending=False)
