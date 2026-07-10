<h1 align="center">🛍️ Enterprise Retail Intelligence Platform (ERIP)</h1>

<p align="center">
  <b>An end-to-end retail analytics project — from a 2.87M-row synthetic data warehouse to an interactive executive BI dashboard.</b><br>
  <sub>Data generation → PostgreSQL star schema → Python analytics engine → executive dashboard & business recommendations.</sub>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="pandas" src="https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-star%20schema-4169E1?logo=postgresql&logoColor=white">
  <img alt="SQL" src="https://img.shields.io/badge/SQL-window%20functions%20%C2%B7%20CTEs-025E8C">
  <img alt="scikit-learn" src="https://img.shields.io/badge/scikit--learn-churn%20model-F7931E?logo=scikitlearn&logoColor=white">
  <img alt="Data Quality" src="https://img.shields.io/badge/Data%20Quality-100%2F100-0ca30c">
</p>

---

## 📌 1. Project overview

ERIP is a **complete, runnable data-analytics & ML pipeline** built around a realistic
enterprise retail business: **5 years of trading (2021–2025), 10 countries, 60,000
registered customers (46,000 active buyers), 6,000 products and ~500,000 orders** —
**$237M in revenue** and **$75.9M in gross profit**.

It was built to demonstrate the **full analytics workflow a company actually needs**:
generate and model data → validate it → engineer features → run analysis → **train a
churn model** → and turn the numbers into an **interactive dashboard and specific,
$-quantified business recommendations**.

> **▶️ Live dashboard:** open [`reports/dashboard.html`](reports/dashboard.html) in any
> browser — a self-contained, zero-dependency executive BI dashboard (light/dark,
> mobile-responsive, interactive drill-downs). Every figure in it is computed by
> [`scripts/run_analytics.py`](scripts/run_analytics.py) over the real 2.87M records.

---

## 🎯 2. Business problem

A multi-national retailer needs to answer, from one place:

| Question | Where it's answered |
|---|---|
| Are we growing, and what's next quarter? | Revenue trend + 6-month forecast |
| Which customers should we invest in / win back? | RFM segmentation + CRM playbooks |
| Do new customers stick around? | Monthly cohort-retention heatmap |
| Which products and categories actually make money? | ABC (Pareto) + category profitability |
| Which markets and channels drive revenue? | Geographic + channel analysis |
| Which marketing channels pay back? | ROAS by channel + acquisition funnel |
| **Which customers are about to churn?** | **Gradient-boosting churn model (ROC-AUC 0.81)** |
| **What is *actually* driving revenue?** | **Correlation analysis** |

---

## 🧭 3. Key insights (the story the data tells)

1. **Revenue concentrates in a few "whale" customers.** The top segment — **Champions,
   ~20% of buyers — drives 55% of revenue** at ~$14K average spend, while the bottom
   half of customers contributes <10%. → *Protect and grow the Champions; don't discount them.*
2. **$31.6M of revenue is at churn risk — and it's predictable.** A gradient-boosting
   model (**ROC-AUC 0.81**) flags **~10,000 High/Critical-risk customers**; recency is
   the dominant driver. → *A campaign on the top-3 risk deciles reaches 76% of churners
   while contacting only 30% of the base.*
3. **A classic Pareto catalog.** Just **22% of products (Class A) generate 80% of
   revenue.** → *Focus stock, pricing and merchandising on ~1,340 SKUs.*
4. **Organic traffic — not ad spend — drives revenue.** Monthly website visitors
   correlate **0.77** with revenue; paid-campaign spend shows **no relationship (−0.05)**.
   → *Invest in SEO/CRO before scaling paid media.*
5. **Marketing mix is misallocated.** Affiliate returns **$24 per $1** while Search &
   Social return **~$9**. Rebalancing spend at constant budget is worth an estimated
   **$1.5–2.0M/yr**.

---

## 🖼️ 4. Dashboard preview

The dashboard ships six analyst views — Overview, Customers, Products, Geography,
Marketing, and a Data-Quality scorecard:

| View | What it shows |
|---|---|
| **Overview** | KPI strip · revenue trajectory + forecast · category mix · channel split · annual growth |
| **Customers** | RFM segmentation with clickable CRM playbooks · monthly cohort-retention heatmap |
| **Products** | ABC/Pareto classification · category profitability · top-10 SKUs |
| **Geography** | Revenue by market · full market-detail table |
| **Marketing** | ROAS by channel · acquisition funnel · reallocation recommendation |
| **Churn ML** | ROC curve · feature importance · gains-by-decile · risk tiers & revenue exposure |
| **Data Quality** | 100/100 validation scorecard · pipeline lineage |

*Built with vanilla JS + hand-authored SVG — **no chart libraries** — so it renders
anywhere with no build step or CDN dependency.*

---

## 🗂️ 5. Dataset

Generated entirely with NumPy/pandas (no external API), with **realistic seasonality,
YoY growth, geography and pricing logic** rather than uniform randomness — so the
analytics have genuine signal to discover. **18 tables · ~2.87M rows · ~49 MB compressed.**

| Domain | Tables |
|---|---|
| **Dimensions** | customers, products, stores, employees, suppliers, coupons, holiday calendar |
| **Sales facts** | orders (500K), order_items (1.09M), payments, returns, shipping |
| **Engagement** | reviews (150K), marketing_campaigns |
| **Operations & context** | inventory, website_traffic, weather, economic_indicators |

```bash
python scripts/generate_data.py                # full dataset (~40s)
python scripts/generate_data.py --sample-only  # tiny dataset for fast tests (~1s)
```

---

## 🧹 6. Data cleaning & validation

Before any analysis runs, the pipeline executes an **automated 32-check quality gate**
([`src/erip/analytics/quality.py`](src/erip/analytics/quality.py)) across five families,
producing a single **0–100 quality score (100/100)**:

| Family | Example checks |
|---|---|
| **Completeness** | no nulls in business-critical columns (order totals, keys, dates) |
| **Uniqueness** | no duplicate primary keys |
| **Referential integrity** | every `order_item` → valid `order` / `product`; no orphan FKs |
| **Validity** | non-negative money, `price > cost`, ratings ∈ [1,5], age ∈ [18,100] |
| **Consistency** | every order reconciles to ≥1 line item |

The same logic exists in SQL ([`sql/queries/data_cleaning_validation.sql`](sql/queries/data_cleaning_validation.sql)) — run it against the warehouse or in Python without a live DB.

---

## 🛠️ 7. Feature engineering

[`src/erip/analytics/features.py`](src/erip/analytics/features.py) builds analysis-ready base tables:

- **Customer RFM table** — recency, frequency, monetary + quintile scores (1–5),
  tenure, AOV, and an **11-cell RFM value segment** (Champions, At-Risk, Hibernating…)
  used across the dashboard and CRM recommendations.
- **Revenue-status filter** — realised-revenue orders only (excludes Cancelled/Refunded),
  so KPIs reflect money actually earned.
- **Monthly revenue time series** with MoM and **YoY growth** derived features.

---

## 📊 8. Analytics implemented

[`src/erip/analytics/metrics.py`](src/erip/analytics/metrics.py) — 12 analysis blocks,
each answering a business question:

`Executive KPIs` · `Monthly trend & YoY` · `RFM segmentation` · `Cohort retention` ·
`Geographic performance` · `Category / product ABC (Pareto)` · `Channel mix` ·
`Marketing ROAS & funnel` · `Returns & quality` · `6-month revenue forecast`
(seasonal-naïve + linear trend) · `Driver correlations`.

---

## 🤖 9. Machine learning — customer churn prediction

[`src/erip/ml/churn.py`](src/erip/ml/churn.py) trains a **point-in-time, leakage-free
churn model**. Standing at an observation date (30 Jun 2025), it predicts which
active customers will make **no purchase in the following 6 months**.

* **No leakage by construction** — every feature is computed strictly *on or before*
  the observation date; the label strictly *after* it.
* **Model selection** — Logistic Regression vs. Histogram Gradient Boosting, chosen by
  5-fold cross-validated ROC-AUC. Gradient Boosting won.
* **Honest evaluation** on a held-out test set:

  | Metric | Value |
  |---|---|
  | ROC-AUC | **0.81** |
  | PR-AUC | **0.76** (vs 0.45 baseline) |
  | Precision / Recall | 0.70 / 0.71 |
  | Top-decile lift | **1.9×** |

* **Explainability** — permutation importance shows **recency** is the dominant churn
  driver, followed by purchase frequency and tenure — exactly what retention theory predicts.
* **Actionability** — the full base is scored into Low/Medium/High/Critical risk tiers;
  **High + Critical customers hold $31.6M of historic revenue**, turning the model into a
  prioritised retention worklist.

```bash
python scripts/train_churn_model.py     # → models/trained/churn_model.joblib + reports/churn_model.json
```

---

## 🏗️ 10. Architecture

```
Raw generators ─▶ 18 gzip-CSV tables (2.87M rows)  [per-customer lifecycle model]
     │                    │
     │             ┌──────┴───────────────────────────────┐
     │             ▼                                       ▼
     │      PostgreSQL star schema              Python analytics engine
     │      (DDL · views · procs · triggers)    src/erip/analytics/
     │             │                             ├─ loader.py   (typed load)
     │             │                             ├─ quality.py  (32 checks)
     │             │                             ├─ features.py (RFM, cohorts)
     │             │                             └─ metrics.py  (12 analyses)
     │             │                                       │
     │             │                             src/erip/ml/  (churn model)
     │             │                             └─ churn.py    (leakage-free, ROC-AUC 0.81)
     │             ▼                                       ▼
     └───▶ business_queries.sql        reports/{analytics_summary,churn_model}.json
                                                           │
                                                           ▼
                                    reports/dashboard.html  (interactive BI + ML)
```

**Design principles:** single source of config ([`settings.py`](src/erip/config/settings.py)),
one place per transformation, production-style logging, JSON contract between the
analytics/ML engines and the presentation layer (so the dashboard never touches raw data).

---

## 🚀 11. Quickstart

```bash
# 1. Environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Generate the data warehouse (~40s)
python scripts/generate_data.py

# 3. Run the analytics pipeline  → reports/analytics_summary.json
python scripts/run_analytics.py

# 4. Train the churn model        → models/trained/churn_model.joblib + reports/churn_model.json
python scripts/train_churn_model.py

# 5. Open the dashboard
open reports/dashboard.html          # macOS   (xdg-open on Linux)

# 6. (Optional) run the tests
pytest -q
```

**Load into PostgreSQL (optional):**
```bash
createdb erip_dw
psql -d erip_dw -f sql/schema/01_create_star_schema.sql
psql -d erip_dw -f sql/schema/02_populate_dim_date.sql
psql -d erip_dw -f sql/schema/03_load_data.sql
psql -d erip_dw -f sql/views/views_procedures_triggers.sql
psql -d erip_dw -f sql/queries/business_queries.sql
```

---

## 📁 12. Folder structure

```
ERIP/
├── data/{raw,sample,processed}/      # gzip-CSV warehouse + engineered features + churn scores
├── src/erip/
│   ├── config/settings.py            # single source of scale/paths/DB config
│   ├── data_generation/              # 8 vectorized generators (per-customer lifecycle model)
│   ├── analytics/                    # ⭐ loader · quality · features · metrics
│   ├── ml/                           # ⭐ churn model (leakage-free, model selection, scoring)
│   └── utils/logger.py               # rotating-file production logger
├── sql/
│   ├── schema/                       # star-schema DDL, dim_date, load, partitioning
│   ├── views/                        # views · materialized views · procs · triggers
│   └── queries/                      # 12 business queries + data-quality checks
├── scripts/
│   ├── generate_data.py              # build the warehouse
│   ├── run_analytics.py              # ⭐ end-to-end analytics orchestrator
│   └── train_churn_model.py          # ⭐ churn training + scoring orchestrator
├── models/trained/churn_model.joblib # serialized sklearn pipeline
├── tests/unit/                       # pytest suite (analytics + ML), 12 tests
├── reports/
│   ├── analytics_summary.json        # computed metrics (dashboard data contract)
│   ├── churn_model.json              # model metrics, importances, lift, ROC
│   ├── EXECUTIVE_SUMMARY.md          # written insight report
│   └── dashboard.html                # ⭐ interactive executive BI + ML dashboard
└── DELIVERABLES.md                   # improvements log, resume bullets, interview Q&A
```

---

## 🧰 13. Tech stack

**Python 3.12** · pandas · NumPy · **scikit-learn** · **PostgreSQL** (star schema, window
functions, CTEs, stored procs, triggers, materialized views) · vanilla-JS + SVG visual
layer · pytest.

---

## 🧠 14. Skills demonstrated

`SQL (window functions, CTEs, star-schema modeling)` · `Python / pandas` ·
`Data cleaning & validation` · `Feature engineering` · `Exploratory data analysis` ·
`RFM & cohort analysis` · `Time-series & forecasting` · `Predictive modeling (churn, model
selection, evaluation, explainability)` · `Statistical thinking (correlation)` ·
`Data visualization & dashboard development` · `Business intelligence & storytelling` ·
`Reproducible, modular, tested pipelines`.

---

## 🔮 15. Future enhancements

- **More models** — demand forecasting (Prophet/XGBoost), a market-basket recommender,
  and CLV regression per segment (the churn base table is already ML-ready).
- **Orchestration** — schedule the pipeline with Airflow / Prefect; add dbt for
  warehouse transformations.
- **Serving** — a FastAPI endpoint exposing the metrics + churn scores; deploy the
  dashboard to GitHub Pages / Netlify.
- **CI** — GitHub Actions running `pytest` + the quality gate on every push.

See [`DELIVERABLES.md`](DELIVERABLES.md) for the full improvement log, résumé bullet
points, and interview preparation.

---

<p align="center"><sub>Built as a portfolio-grade demonstration of the end-to-end data-analytics workflow.</sub></p>

# To start it 
cd ~/Downloads
unzip ERIP-Enterprise-Retail-Intelligence-Platform.zip
cd ERIP
python3 -m venv .venv && source .venv/bin/activate   # recreate the venv
pip install -r requirements.txt                       # ~30s
# then anything works:
python scripts/run_analytics.py      # or train_churn_model.py
open reports/dashboard.html          # dashboard works instantly (self-contained)

