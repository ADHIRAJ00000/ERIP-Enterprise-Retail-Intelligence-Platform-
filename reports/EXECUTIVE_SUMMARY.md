# Executive Summary — Enterprise Retail Intelligence Platform

**Reporting period:** Jan 2021 – Dec 2025 (5 years) · **Markets:** 10 countries · **Source:** 2.87M-record data warehouse
**Data quality:** 100/100 (32/32 automated checks passed)

---

## Headline performance

| KPI | Value |
|---|---|
| Total revenue | **$237.1M** |
| Gross profit | **$75.9M** (32.0% blended margin) |
| Orders | **410,909** |
| Active customers | **46,101** (of 60,000 registered) |
| Average order value | **$577** |
| Revenue growth (2025 vs 2024) | **+3.9%** |
| Repeat-purchase rate | **81%** |

Revenue grew strongly as the customer base scaled — from under $1M/month in early 2021
to **~$7.8M/month by end-2025** — with a pronounced, repeatable **November–December peak**
(holiday demand) and a maturing growth rate.

---

## Six findings that matter

### 1. Revenue concentrates in a few "whale" customers
The top RFM segment — **Champions, ~20% of buyers — drives 55% of revenue** at ~$14K
average lifetime spend, while the bottom half of customers contributes under 10%.
**Action:** protect and grow Champions with VIP treatment and referrals; never discount them.

### 2. $31.6M of revenue is at churn risk — and it's predictable
A gradient-boosting churn model (**ROC-AUC 0.81**, PR-AUC 0.76) identifies **~10,000
High/Critical-risk customers** holding **$31.6M of historic revenue**. Recency (time since
last order) is the dominant driver.
**Action:** target the top-3 risk deciles — that reaches **76% of predicted churners while
contacting only 30% of the base**. Saving even 10% of the at-risk revenue is ~$3.2M.

### 3. The catalog is textbook Pareto — 22% of SKUs make 80% of revenue
ABC classification puts **1,344 of 6,000 products in Class A (80% of revenue)**.
**Action:** guarantee availability and pricing discipline on Class-A SKUs; rationalise the
3,000-product Class-C long tail (5% of revenue) to cut carrying cost.

### 4. Organic traffic — not ad spend — is the revenue engine
Monthly **website visitors correlate 0.77** with revenue; **marketing spend shows no
relationship (−0.05)**.
**Action:** prioritise SEO / conversion-rate optimisation; treat paid media as incremental.

### 5. Growth is a volume game, not a margin game
Gross margin is a flat **31–33% across every category**; category value is set by **units
sold** — Electronics alone is **36% of revenue**, the top 3 categories 71%.
**Action:** growth investment should target traffic and conversion, not markup.

### 6. Marketing budget is misallocated
**Affiliate returns $24 per $1; Display ~$19; Search & Social only ~$9.**
**Action:** rebalancing spend toward Affiliate/Display at constant budget is worth an
estimated **$1.5–2.0M/yr**.

---

## Recommendation summary

| Priority | Recommendation | Estimated impact |
|---|---|---|
| 🔴 High | Retention campaign on model-flagged High/Critical churn risk | Protects up to $31.6M; ~$3.2M realistically recoverable |
| 🔴 High | Rebalance marketing mix toward Affiliate/Display | +$1.5–2.0M/yr |
| 🟠 Medium | VIP program for Champions (55% of revenue) | Protects the core |
| 🟠 Medium | Shift growth budget from paid media to SEO/CRO | Higher-ROI acquisition |
| 🟠 Medium | Rationalise Class-C long tail; protect Class-A availability | Lower carrying cost |
| 🟢 Ongoing | Staff & stock for the Nov–Dec peak | Capture seasonal upside |

*All figures produced by `scripts/run_analytics.py` and `scripts/train_churn_model.py`
over the full warehouse and are reproducible end-to-end. See `reports/dashboard.html` for
the interactive view.*
