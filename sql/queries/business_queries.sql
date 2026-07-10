-- =============================================================================
-- ERIP — Business Analytics Query Library
-- Demonstrates: CTEs, window functions, ranking, joins, YoY/QoQ growth,
-- retention, CLV, inventory turnover, basket size, Pareto/ABC analysis.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. TOP 20 CUSTOMERS BY LIFETIME REVENUE
-- -----------------------------------------------------------------------------
SELECT
    c.customer_id,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.country,
    c.customer_segment,
    COUNT(DISTINCT o.order_id)         AS total_orders,
    ROUND(SUM(oi.line_revenue), 2)     AS lifetime_revenue,
    ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value
FROM dim_customers c
JOIN fact_orders o       ON o.customer_id = c.customer_id
JOIN fact_order_items oi ON oi.order_id = o.order_id
WHERE o.order_status NOT IN ('Cancelled')
GROUP BY c.customer_id, c.first_name, c.last_name, c.country, c.customer_segment
ORDER BY lifetime_revenue DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 2. TOP 20 PRODUCTS BY REVENUE, WITH RANK PER CATEGORY (window function)
-- -----------------------------------------------------------------------------
WITH product_revenue AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        SUM(oi.line_revenue) AS total_revenue,
        SUM(oi.quantity)     AS units_sold
    FROM fact_order_items oi
    JOIN dim_products p ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name, p.category
)
SELECT
    category,
    product_name,
    total_revenue,
    units_sold,
    RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS rank_in_category,
    RANK() OVER (ORDER BY total_revenue DESC)                       AS rank_overall
FROM product_revenue
QUALIFY rank_overall <= 20
ORDER BY total_revenue DESC;
-- Note: QUALIFY is not native to PostgreSQL (it's a Snowflake/BigQuery extension).
-- PostgreSQL-portable equivalent below:

WITH product_revenue AS (
    SELECT
        p.product_id, p.product_name, p.category,
        SUM(oi.line_revenue) AS total_revenue,
        SUM(oi.quantity) AS units_sold
    FROM fact_order_items oi
    JOIN dim_products p ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name, p.category
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY category ORDER BY total_revenue DESC) AS rank_in_category,
           RANK() OVER (ORDER BY total_revenue DESC) AS rank_overall
    FROM product_revenue
)
SELECT * FROM ranked WHERE rank_overall <= 20 ORDER BY total_revenue DESC;

-- -----------------------------------------------------------------------------
-- 3. MONTHLY REVENUE WITH MoM GROWTH % (window function: LAG)
-- -----------------------------------------------------------------------------
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', oi.order_date) AS month,
        SUM(oi.line_revenue) AS revenue
    FROM fact_order_items oi
    GROUP BY 1
)
SELECT
    month,
    revenue,
    LAG(revenue) OVER (ORDER BY month) AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY month))
        / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) * 100, 2
    ) AS mom_growth_pct
FROM monthly_revenue
ORDER BY month;

-- -----------------------------------------------------------------------------
-- 4. QUARTERLY REVENUE WITH YoY COMPARISON
-- -----------------------------------------------------------------------------
WITH quarterly_revenue AS (
    SELECT
        EXTRACT(YEAR FROM oi.order_date)::INT AS yr,
        EXTRACT(QUARTER FROM oi.order_date)::INT AS qtr,
        SUM(oi.line_revenue) AS revenue
    FROM fact_order_items oi
    GROUP BY 1, 2
)
SELECT
    yr, qtr, revenue,
    LAG(revenue) OVER (PARTITION BY qtr ORDER BY yr) AS revenue_same_qtr_prior_year,
    ROUND(
        (revenue - LAG(revenue) OVER (PARTITION BY qtr ORDER BY yr))
        / NULLIF(LAG(revenue) OVER (PARTITION BY qtr ORDER BY yr), 0) * 100, 2
    ) AS yoy_growth_pct
FROM quarterly_revenue
ORDER BY yr, qtr;

-- -----------------------------------------------------------------------------
-- 5. CUSTOMER RETENTION — month-over-month active customer overlap
-- -----------------------------------------------------------------------------
WITH monthly_customers AS (
    SELECT DISTINCT
        DATE_TRUNC('month', o.order_date) AS month,
        o.customer_id
    FROM fact_orders o
    WHERE o.order_status != 'Cancelled'
),
retention AS (
    SELECT
        curr.month,
        COUNT(DISTINCT curr.customer_id) AS active_customers,
        COUNT(DISTINCT prev.customer_id) AS retained_from_prior_month
    FROM monthly_customers curr
    LEFT JOIN monthly_customers prev
        ON prev.customer_id = curr.customer_id
        AND prev.month = curr.month - INTERVAL '1 month'
    GROUP BY curr.month
)
SELECT
    month,
    active_customers,
    retained_from_prior_month,
    ROUND(retained_from_prior_month::NUMERIC / NULLIF(LAG(active_customers) OVER (ORDER BY month), 0) * 100, 2) AS retention_rate_pct
FROM retention
ORDER BY month;

-- -----------------------------------------------------------------------------
-- 6. CUSTOMER LIFETIME VALUE (CLV) — simple historical CLV
-- -----------------------------------------------------------------------------
SELECT
    c.customer_id,
    c.customer_segment,
    MIN(o.order_date) AS first_purchase,
    MAX(o.order_date) AS last_purchase,
    (MAX(o.order_date) - MIN(o.order_date)) AS customer_lifespan_days,
    COUNT(DISTINCT o.order_id) AS total_orders,
    ROUND(SUM(oi.line_revenue), 2) AS total_revenue,
    ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value,
    ROUND(
        SUM(oi.line_revenue) / NULLIF(GREATEST(MAX(o.order_date) - MIN(o.order_date), 1), 0) * 365, 2
    ) AS estimated_annualized_clv
FROM dim_customers c
JOIN fact_orders o ON o.customer_id = c.customer_id
JOIN fact_order_items oi ON oi.order_id = o.order_id
GROUP BY c.customer_id, c.customer_segment
ORDER BY estimated_annualized_clv DESC;

-- -----------------------------------------------------------------------------
-- 7. INVENTORY TURNOVER RATIO by product (COGS / Avg Inventory Value)
-- -----------------------------------------------------------------------------
WITH cogs AS (
    SELECT product_id, SUM(line_cost) AS total_cogs
    FROM fact_order_items
    GROUP BY product_id
),
avg_inventory_value AS (
    SELECT
        i.product_id,
        AVG(i.stock_on_hand * p.unit_cost) AS avg_inventory_value
    FROM fact_inventory i
    JOIN dim_products p ON p.product_id = i.product_id
    GROUP BY i.product_id
)
SELECT
    p.product_id, p.product_name, p.category,
    COALESCE(c.total_cogs, 0) AS total_cogs,
    COALESCE(a.avg_inventory_value, 0) AS avg_inventory_value,
    ROUND(c.total_cogs / NULLIF(a.avg_inventory_value, 0), 2) AS inventory_turnover_ratio
FROM dim_products p
LEFT JOIN cogs c ON c.product_id = p.product_id
LEFT JOIN avg_inventory_value a ON a.product_id = p.product_id
WHERE a.avg_inventory_value > 0
ORDER BY inventory_turnover_ratio DESC
LIMIT 50;

-- -----------------------------------------------------------------------------
-- 8. AVERAGE BASKET SIZE (items per order) by channel
-- -----------------------------------------------------------------------------
SELECT
    o.channel,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(oi.order_item_id) AS total_line_items,
    ROUND(COUNT(oi.order_item_id)::NUMERIC / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_basket_size,
    ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value
FROM fact_orders o
JOIN fact_order_items oi ON oi.order_id = o.order_id
GROUP BY o.channel;

-- -----------------------------------------------------------------------------
-- 9. PROFIT MARGIN BY CATEGORY
-- -----------------------------------------------------------------------------
SELECT
    p.category,
    ROUND(SUM(oi.line_revenue), 2) AS revenue,
    ROUND(SUM(oi.line_cost), 2)    AS cost,
    ROUND(SUM(oi.line_profit), 2)  AS profit,
    ROUND(SUM(oi.line_profit) / NULLIF(SUM(oi.line_revenue), 0) * 100, 2) AS margin_pct
FROM fact_order_items oi
JOIN dim_products p ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY profit DESC;

-- -----------------------------------------------------------------------------
-- 10. REGIONAL SALES PERFORMANCE
-- -----------------------------------------------------------------------------
SELECT
    c.country,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT c.customer_id) AS unique_customers,
    ROUND(SUM(oi.line_revenue), 2) AS total_revenue,
    ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value
FROM dim_customers c
JOIN fact_orders o ON o.customer_id = c.customer_id
JOIN fact_order_items oi ON oi.order_id = o.order_id
GROUP BY c.country
ORDER BY total_revenue DESC;

-- -----------------------------------------------------------------------------
-- 11. PARETO / ABC ANALYSIS — what % of products drive 80% of revenue
-- -----------------------------------------------------------------------------
WITH product_rev AS (
    SELECT p.product_id, p.product_name, SUM(oi.line_revenue) AS revenue
    FROM fact_order_items oi
    JOIN dim_products p ON p.product_id = oi.product_id
    GROUP BY p.product_id, p.product_name
),
ranked AS (
    SELECT *,
           SUM(revenue) OVER (ORDER BY revenue DESC) AS running_total,
           SUM(revenue) OVER () AS grand_total,
           ROW_NUMBER() OVER (ORDER BY revenue DESC) AS rn,
           COUNT(*) OVER () AS total_products
    FROM product_rev
)
SELECT
    product_id, product_name, revenue,
    ROUND(running_total / grand_total * 100, 2) AS cumulative_revenue_pct,
    ROUND(rn::NUMERIC / total_products * 100, 2) AS cumulative_product_pct,
    CASE
        WHEN running_total / grand_total <= 0.80 THEN 'A'
        WHEN running_total / grand_total <= 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM ranked
ORDER BY revenue DESC;

-- -----------------------------------------------------------------------------
-- 12. GROWTH RATE — rolling 3-month moving average revenue (window frame)
-- -----------------------------------------------------------------------------
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_date) AS month, SUM(line_revenue) AS revenue
    FROM fact_order_items
    GROUP BY 1
)
SELECT
    month,
    revenue,
    ROUND(AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3mo_avg
FROM monthly
ORDER BY month;
