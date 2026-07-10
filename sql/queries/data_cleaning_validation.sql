-- =============================================================================
-- ERIP — Data Cleaning & Validation Queries
-- Run after each load to catch data quality issues before they reach BI tools.
-- =============================================================================

-- 1. Duplicate natural keys (should return 0 rows on a healthy load)
SELECT order_id, COUNT(*) FROM fact_orders GROUP BY order_id HAVING COUNT(*) > 1;
SELECT customer_id, COUNT(*) FROM dim_customers GROUP BY customer_id HAVING COUNT(*) > 1;

-- 2. Orphaned fact rows (referential integrity check beyond FK constraints —
--    useful pre-load on staging tables before constraints are enforced)
SELECT oi.order_id
FROM fact_order_items oi
LEFT JOIN fact_orders o ON o.order_id = oi.order_id
WHERE o.order_id IS NULL;

-- 3. Negative or impossible values
SELECT * FROM fact_order_items WHERE line_revenue < 0 OR quantity <= 0;
SELECT * FROM dim_products WHERE unit_price <= 0 OR unit_cost < 0;
SELECT * FROM dim_customers WHERE age < 13 OR age > 100;

-- 4. Orders with no line items (data gap)
SELECT o.order_id
FROM fact_orders o
LEFT JOIN fact_order_items oi ON oi.order_id = o.order_id
WHERE oi.order_item_id IS NULL;

-- 5. Future-dated records (should never occur in historical fact data)
SELECT * FROM fact_orders WHERE order_date > CURRENT_DATE;

-- 6. Outlier detection — orders more than 4 standard deviations above mean
--    order value (candidate fraud/data-entry-error review queue)
WITH stats AS (
    SELECT AVG(total_amount) AS mean_amt, STDDEV(total_amount) AS std_amt FROM fact_orders
)
SELECT o.*
FROM fact_orders o, stats
WHERE o.total_amount > stats.mean_amt + 4 * stats.std_amt
ORDER BY o.total_amount DESC;

-- 7. Standardize text casing/whitespace (example UPDATE pattern — run on staging, not prod, without review)
-- UPDATE dim_customers SET city = INITCAP(TRIM(city));
-- UPDATE dim_products  SET category = INITCAP(TRIM(category));

-- 8. NULL audit across key dimension columns
SELECT
    COUNT(*) FILTER (WHERE country IS NULL) AS null_country,
    COUNT(*) FILTER (WHERE signup_date IS NULL) AS null_signup_date,
    COUNT(*) FILTER (WHERE customer_segment IS NULL) AS null_segment
FROM dim_customers;
