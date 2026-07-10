-- =============================================================================
-- ERIP — Views, Materialized Views, Stored Procedures, Triggers
-- =============================================================================

-- -----------------------------------------------------------------------------
-- VIEW: vw_order_summary — denormalized order-level view for BI tools
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_order_summary AS
SELECT
    o.order_id,
    o.order_date,
    c.customer_id,
    c.customer_segment,
    c.country AS customer_country,
    o.channel,
    o.order_status,
    o.payment_method,
    o.total_amount,
    COUNT(oi.order_item_id) AS line_item_count,
    SUM(oi.line_profit) AS total_profit
FROM fact_orders o
JOIN dim_customers c ON c.customer_id = o.customer_id
LEFT JOIN fact_order_items oi ON oi.order_id = o.order_id
GROUP BY o.order_id, o.order_date, c.customer_id, c.customer_segment,
         c.country, o.channel, o.order_status, o.payment_method, o.total_amount;

-- -----------------------------------------------------------------------------
-- VIEW: vw_product_performance
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_product_performance AS
SELECT
    p.product_id, p.product_name, p.category, p.subcategory, p.brand,
    SUM(oi.quantity) AS units_sold,
    SUM(oi.line_revenue) AS total_revenue,
    SUM(oi.line_profit) AS total_profit,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    COUNT(DISTINCT r.review_id) AS review_count
FROM dim_products p
LEFT JOIN fact_order_items oi ON oi.product_id = p.product_id
LEFT JOIN fact_reviews r ON r.product_id = p.product_id
GROUP BY p.product_id, p.product_name, p.category, p.subcategory, p.brand;

-- -----------------------------------------------------------------------------
-- VIEW: vw_store_performance
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_store_performance AS
SELECT
    s.store_id, s.store_name, s.store_type, s.country, s.city,
    COUNT(DISTINCT o.order_id) AS total_orders,
    SUM(oi.line_revenue) AS total_revenue,
    ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_order_value
FROM dim_stores s
LEFT JOIN fact_orders o ON o.store_id = s.store_id
LEFT JOIN fact_order_items oi ON oi.order_id = o.order_id
GROUP BY s.store_id, s.store_name, s.store_type, s.country, s.city;

-- -----------------------------------------------------------------------------
-- MATERIALIZED VIEW: mv_daily_sales_summary
-- Refreshed nightly by the Airflow ETL DAG — backs the executive dashboard's
-- "Sales Trend" visual without recomputing aggregates on every page load.
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_sales_summary AS
SELECT
    oi.order_date,
    COUNT(DISTINCT oi.order_id) AS order_count,
    SUM(oi.quantity) AS units_sold,
    SUM(oi.line_revenue) AS revenue,
    SUM(oi.line_profit) AS profit
FROM fact_order_items oi
GROUP BY oi.order_date
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_sales_date ON mv_daily_sales_summary (order_date);

-- Refresh command (run via cron / Airflow DAG nightly):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;

-- -----------------------------------------------------------------------------
-- MATERIALIZED VIEW: mv_customer_rfm — precomputed RFM base metrics
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_rfm AS
SELECT
    c.customer_id,
    MAX(o.order_date) AS last_order_date,
    (DATE '2025-12-31' - MAX(o.order_date)) AS recency_days,
    COUNT(DISTINCT o.order_id) AS frequency,
    SUM(oi.line_revenue) AS monetary
FROM dim_customers c
JOIN fact_orders o ON o.customer_id = c.customer_id
JOIN fact_order_items oi ON oi.order_id = o.order_id
WHERE o.order_status != 'Cancelled'
GROUP BY c.customer_id
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_rfm_customer ON mv_customer_rfm (customer_id);

-- -----------------------------------------------------------------------------
-- STORED PROCEDURE: sp_refresh_all_materialized_views
-- Called by the nightly Airflow DAG after ETL load completes.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_refresh_all_materialized_views()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_customer_rfm;
    RAISE NOTICE 'Materialized views refreshed at %', clock_timestamp();
END;
$$;

-- -----------------------------------------------------------------------------
-- STORED PROCEDURE: sp_get_customer_clv
-- Parameterized procedure returning CLV for a single customer (used by the
-- FastAPI /customers/{id}/clv endpoint).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_get_customer_clv(p_customer_id VARCHAR)
RETURNS TABLE (
    customer_id VARCHAR,
    total_orders BIGINT,
    total_revenue NUMERIC,
    avg_order_value NUMERIC,
    estimated_annual_clv NUMERIC
)
LANGUAGE sql
AS $$
    SELECT
        c.customer_id,
        COUNT(DISTINCT o.order_id),
        ROUND(SUM(oi.line_revenue), 2),
        ROUND(SUM(oi.line_revenue) / NULLIF(COUNT(DISTINCT o.order_id), 0), 2),
        ROUND(
            SUM(oi.line_revenue) / NULLIF(GREATEST(MAX(o.order_date) - MIN(o.order_date), 1), 0) * 365, 2
        )
    FROM dim_customers c
    JOIN fact_orders o ON o.customer_id = c.customer_id
    JOIN fact_order_items oi ON oi.order_id = o.order_id
    WHERE c.customer_id = p_customer_id
    GROUP BY c.customer_id;
$$;

-- Usage: SELECT * FROM sp_get_customer_clv('CUST00012345');

-- -----------------------------------------------------------------------------
-- TRIGGER: trg_validate_order_item — data quality guard at insert time
-- Rejects line items with non-positive revenue (defensive data quality check,
-- complements the upstream Python validation layer).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validate_order_item()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.line_revenue < 0 THEN
        RAISE EXCEPTION 'fact_order_items: line_revenue cannot be negative (order_item_id=%)', NEW.order_item_id;
    END IF;
    IF NEW.quantity <= 0 THEN
        RAISE EXCEPTION 'fact_order_items: quantity must be positive (order_item_id=%)', NEW.order_item_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_order_item ON fact_order_items;
CREATE TRIGGER trg_validate_order_item
    BEFORE INSERT OR UPDATE ON fact_order_items
    FOR EACH ROW
    EXECUTE FUNCTION fn_validate_order_item();

-- -----------------------------------------------------------------------------
-- TRIGGER: trg_orders_audit — track last-modified timestamp on fact_orders
-- -----------------------------------------------------------------------------
ALTER TABLE fact_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now();

CREATE OR REPLACE FUNCTION fn_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_orders_audit ON fact_orders;
CREATE TRIGGER trg_orders_audit
    BEFORE UPDATE ON fact_orders
    FOR EACH ROW
    EXECUTE FUNCTION fn_touch_updated_at();
