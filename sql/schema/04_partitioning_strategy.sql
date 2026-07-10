-- =============================================================================
-- ERIP — Partitioning Strategy (reference implementation)
-- =============================================================================
-- fact_order_items is the highest-volume, fastest-growing table and is
-- almost always queried with a date filter (BI dashboards, monthly reports).
-- RANGE partitioning by order_date lets PostgreSQL prune irrelevant
-- partitions automatically, dramatically speeding up date-bound queries
-- at scale (this matters once the table reaches tens of millions of rows
-- in a true 5M-orders/5-year deployment).
--
-- NOTE: This is a reference/alternative implementation. The base schema in
-- 01_create_star_schema.sql creates fact_order_items as a normal table for
-- simplicity; adopt this version instead if you scale to the full enterprise
-- spec (5M+ orders) or need multi-year query performance in production.
-- =============================================================================

CREATE TABLE fact_order_items_partitioned (
    order_item_sk     BIGSERIAL,
    order_item_id      VARCHAR(20) NOT NULL,
    order_id             VARCHAR(20) NOT NULL,
    order_date             DATE NOT NULL,
    product_id                VARCHAR(20) NOT NULL,
    quantity                    SMALLINT NOT NULL,
    unit_price                    NUMERIC(10,2) NOT NULL,
    discount_pct                    NUMERIC(5,4) DEFAULT 0,
    line_revenue                      NUMERIC(12,2) NOT NULL,
    line_cost                           NUMERIC(12,2) NOT NULL,
    line_profit                           NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_item_sk, order_date)
) PARTITION BY RANGE (order_date);

-- One partition per year (could go finer, e.g. monthly, at higher volume)
CREATE TABLE fact_order_items_y2021 PARTITION OF fact_order_items_partitioned
    FOR VALUES FROM ('2021-01-01') TO ('2022-01-01');
CREATE TABLE fact_order_items_y2022 PARTITION OF fact_order_items_partitioned
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE fact_order_items_y2023 PARTITION OF fact_order_items_partitioned
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE fact_order_items_y2024 PARTITION OF fact_order_items_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE fact_order_items_y2025 PARTITION OF fact_order_items_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Default partition catches any out-of-range dates (defensive, avoids load failures)
CREATE TABLE fact_order_items_default PARTITION OF fact_order_items_partitioned DEFAULT;

-- Indexes created on the parent propagate to every partition automatically (PG 11+)
CREATE INDEX idx_part_items_product ON fact_order_items_partitioned (product_id);
CREATE INDEX idx_part_items_order ON fact_order_items_partitioned (order_id);

-- Example query that benefits from partition pruning (planner only scans
-- the 2024 partition instead of the full table):
-- EXPLAIN ANALYZE
-- SELECT SUM(line_revenue) FROM fact_order_items_partitioned
-- WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31';
