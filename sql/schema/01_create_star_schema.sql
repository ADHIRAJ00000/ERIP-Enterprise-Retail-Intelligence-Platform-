-- =============================================================================
-- ERIP — Enterprise Retail Intelligence Platform
-- Data Warehouse Schema (PostgreSQL)
-- Design: Star Schema with conformed dimensions
-- =============================================================================
-- Layer:        Core Dimensional Model
-- Grain:        fact_order_items = 1 row per product per order
-- Conventions:  surrogate keys = <table>_sk (BIGSERIAL), natural/business
--               keys retained as <table>_id (TEXT) for traceability back to
--               source systems, consistent snake_case naming, all timestamps
--               stored as TIMESTAMP (UTC).
-- =============================================================================

-- Drop in dependency-safe order (facts before dims) for idempotent re-runs
DROP TABLE IF EXISTS fact_returns CASCADE;
DROP TABLE IF EXISTS fact_shipping CASCADE;
DROP TABLE IF EXISTS fact_payments CASCADE;
DROP TABLE IF EXISTS fact_order_items CASCADE;
DROP TABLE IF EXISTS fact_orders CASCADE;
DROP TABLE IF EXISTS fact_inventory CASCADE;
DROP TABLE IF EXISTS fact_reviews CASCADE;
DROP TABLE IF EXISTS fact_marketing_campaigns CASCADE;
DROP TABLE IF EXISTS fact_website_traffic CASCADE;
DROP TABLE IF EXISTS fact_weather CASCADE;
DROP TABLE IF EXISTS fact_economic_indicators CASCADE;
DROP TABLE IF EXISTS dim_customers CASCADE;
DROP TABLE IF EXISTS dim_products CASCADE;
DROP TABLE IF EXISTS dim_stores CASCADE;
DROP TABLE IF EXISTS dim_employees CASCADE;
DROP TABLE IF EXISTS dim_suppliers CASCADE;
DROP TABLE IF EXISTS dim_coupons CASCADE;
DROP TABLE IF EXISTS dim_holiday_calendar CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

-- =============================================================================
-- DIMENSION: dim_date  (standard date dimension, generated, not loaded from CSV)
-- =============================================================================
CREATE TABLE dim_date (
    date_sk             INT PRIMARY KEY,             -- YYYYMMDD
    full_date           DATE NOT NULL UNIQUE,
    day_of_week         SMALLINT NOT NULL,
    day_name            VARCHAR(10) NOT NULL,
    day_of_month        SMALLINT NOT NULL,
    day_of_year         SMALLINT NOT NULL,
    week_of_year        SMALLINT NOT NULL,
    month_num            SMALLINT NOT NULL,
    month_name          VARCHAR(10) NOT NULL,
    quarter             SMALLINT NOT NULL,
    year                SMALLINT NOT NULL,
    is_weekend          BOOLEAN NOT NULL,
    fiscal_year         SMALLINT NOT NULL,
    fiscal_quarter      SMALLINT NOT NULL
);

-- =============================================================================
-- DIMENSION: dim_customers
-- =============================================================================
CREATE TABLE dim_customers (
    customer_sk         BIGSERIAL PRIMARY KEY,
    customer_id         VARCHAR(20) NOT NULL UNIQUE,
    first_name          VARCHAR(50),
    last_name           VARCHAR(50),
    email               VARCHAR(150),
    gender              VARCHAR(10),
    age                 SMALLINT,
    country             VARCHAR(60) NOT NULL,
    city                VARCHAR(60),
    currency            CHAR(3),
    signup_date          DATE NOT NULL,
    acquisition_channel  VARCHAR(40),
    customer_segment     VARCHAR(20),
    is_loyalty_member    BOOLEAN DEFAULT FALSE,
    marketing_opt_in     BOOLEAN DEFAULT FALSE,
    -- SCD2 audit columns (slowly changing dimension support)
    effective_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date          DATE DEFAULT NULL,
    is_current            BOOLEAN DEFAULT TRUE,
    loaded_at             TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX idx_customers_country ON dim_customers (country);
CREATE INDEX idx_customers_segment ON dim_customers (customer_segment);
CREATE INDEX idx_customers_signup_date ON dim_customers (signup_date);

-- =============================================================================
-- DIMENSION: dim_suppliers (loaded before products due to FK)
-- =============================================================================
CREATE TABLE dim_suppliers (
    supplier_sk          BIGSERIAL PRIMARY KEY,
    supplier_id           INT NOT NULL UNIQUE,
    supplier_name          VARCHAR(150),
    country                VARCHAR(60),
    reliability_score       NUMERIC(5,2),
    avg_lead_time_days      SMALLINT,
    contract_start_date      DATE,
    is_active                BOOLEAN DEFAULT TRUE
);

-- =============================================================================
-- DIMENSION: dim_products
-- =============================================================================
CREATE TABLE dim_products (
    product_sk           BIGSERIAL PRIMARY KEY,
    product_id            VARCHAR(20) NOT NULL UNIQUE,
    product_name           VARCHAR(200),
    category                VARCHAR(60) NOT NULL,
    subcategory             VARCHAR(60),
    brand                    VARCHAR(60),
    unit_price                NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    unit_cost                 NUMERIC(10,2) NOT NULL CHECK (unit_cost >= 0),
    margin_pct                 NUMERIC(6,2),
    weight_kg                   NUMERIC(8,2),
    launch_date                  DATE,
    is_discontinued                BOOLEAN DEFAULT FALSE,
    rating_avg                      NUMERIC(3,1),
    supplier_id                      INT REFERENCES dim_suppliers (supplier_id)
);
CREATE INDEX idx_products_category ON dim_products (category, subcategory);
CREATE INDEX idx_products_brand ON dim_products (brand);
CREATE INDEX idx_products_discontinued ON dim_products (is_discontinued);

-- =============================================================================
-- DIMENSION: dim_stores
-- =============================================================================
CREATE TABLE dim_stores (
    store_sk              BIGSERIAL PRIMARY KEY,
    store_id                VARCHAR(20) NOT NULL UNIQUE,
    store_name                VARCHAR(150),
    store_type                  VARCHAR(40),
    country                       VARCHAR(60) NOT NULL,
    city                            VARCHAR(60),
    square_footage                    INT,
    opened_date                        DATE,
    is_active                            BOOLEAN DEFAULT TRUE,
    manager_employee_id                   VARCHAR(20)
);
CREATE INDEX idx_stores_country ON dim_stores (country);

-- =============================================================================
-- DIMENSION: dim_employees
-- =============================================================================
CREATE TABLE dim_employees (
    employee_sk            BIGSERIAL PRIMARY KEY,
    employee_id               VARCHAR(20) NOT NULL UNIQUE,
    first_name                  VARCHAR(50),
    last_name                     VARCHAR(50),
    role                            VARCHAR(60),
    store_id                          VARCHAR(20) REFERENCES dim_stores (store_id),
    hire_date                           DATE,
    annual_salary_usd                     NUMERIC(10,2),
    performance_rating                      NUMERIC(3,1),
    is_active                                 BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_employees_store ON dim_employees (store_id);

-- =============================================================================
-- DIMENSION: dim_coupons
-- =============================================================================
CREATE TABLE dim_coupons (
    coupon_sk                BIGSERIAL PRIMARY KEY,
    coupon_id                  VARCHAR(20) NOT NULL UNIQUE,
    coupon_code                  VARCHAR(30),
    discount_type                  VARCHAR(20),
    discount_value                   NUMERIC(8,2),
    issue_date                         DATE,
    expiry_date                          DATE,
    min_purchase_amount                    NUMERIC(10,2),
    times_redeemed                           INT,
    is_active                                  BOOLEAN DEFAULT TRUE
);

-- =============================================================================
-- DIMENSION: dim_holiday_calendar
-- =============================================================================
CREATE TABLE dim_holiday_calendar (
    holiday_sk                 BIGSERIAL PRIMARY KEY,
    holiday_date                 DATE NOT NULL,
    holiday_name                   VARCHAR(80),
    is_major_shopping_event          BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_holiday_date ON dim_holiday_calendar (holiday_date);

-- =============================================================================
-- FACT: fact_orders  (grain: 1 row per order)
-- =============================================================================
CREATE TABLE fact_orders (
    order_sk                BIGSERIAL PRIMARY KEY,
    order_id                  VARCHAR(20) NOT NULL UNIQUE,
    customer_id                 VARCHAR(20) NOT NULL REFERENCES dim_customers (customer_id),
    store_id                      VARCHAR(20),  -- 'ONLINE' sentinel or FK to dim_stores
    order_date                      DATE NOT NULL,
    channel                            VARCHAR(20),
    order_status                         VARCHAR(20),
    payment_method                         VARCHAR(30),
    total_amount                             NUMERIC(12,2) NOT NULL DEFAULT 0
);
CREATE INDEX idx_orders_customer ON fact_orders (customer_id);
CREATE INDEX idx_orders_store ON fact_orders (store_id);
CREATE INDEX idx_orders_date ON fact_orders (order_date);
CREATE INDEX idx_orders_status ON fact_orders (order_status);
-- Composite index supporting the most common BI query pattern: date range + status
CREATE INDEX idx_orders_date_status ON fact_orders (order_date, order_status);

-- =============================================================================
-- FACT: fact_order_items  (grain: 1 row per product per order — finest grain)
-- =============================================================================
CREATE TABLE fact_order_items (
    order_item_sk             BIGSERIAL PRIMARY KEY,
    order_item_id               VARCHAR(20) NOT NULL UNIQUE,
    order_id                      VARCHAR(20) NOT NULL REFERENCES fact_orders (order_id),
    order_date                      DATE NOT NULL,
    product_id                        VARCHAR(20) NOT NULL REFERENCES dim_products (product_id),
    quantity                            SMALLINT NOT NULL CHECK (quantity > 0),
    unit_price                            NUMERIC(10,2) NOT NULL,
    discount_pct                            NUMERIC(5,4) DEFAULT 0,
    line_revenue                              NUMERIC(12,2) NOT NULL,
    line_cost                                   NUMERIC(12,2) NOT NULL,
    line_profit                                   NUMERIC(12,2) NOT NULL
);
CREATE INDEX idx_items_order ON fact_order_items (order_id);
CREATE INDEX idx_items_product ON fact_order_items (product_id);
CREATE INDEX idx_items_date ON fact_order_items (order_date);

-- =============================================================================
-- FACT: fact_payments
-- =============================================================================
CREATE TABLE fact_payments (
    payment_sk                  BIGSERIAL PRIMARY KEY,
    payment_id                    VARCHAR(20) NOT NULL UNIQUE,
    order_id                        VARCHAR(20) NOT NULL REFERENCES fact_orders (order_id),
    payment_date                      DATE NOT NULL,
    amount                              NUMERIC(12,2) NOT NULL,
    payment_method                        VARCHAR(30),
    payment_status                          VARCHAR(20),
    transaction_fee_pct                       NUMERIC(6,4)
);
CREATE INDEX idx_payments_order ON fact_payments (order_id);
CREATE INDEX idx_payments_status ON fact_payments (payment_status);

-- =============================================================================
-- FACT: fact_returns
-- =============================================================================
CREATE TABLE fact_returns (
    return_sk                     BIGSERIAL PRIMARY KEY,
    return_id                       VARCHAR(20) NOT NULL UNIQUE,
    order_id                          VARCHAR(20) NOT NULL REFERENCES fact_orders (order_id),
    order_item_id                       VARCHAR(20) NOT NULL REFERENCES fact_order_items (order_item_id),
    return_date                           DATE NOT NULL,
    return_reason                           VARCHAR(60),
    refund_amount                             NUMERIC(12,2),
    restocked                                   BOOLEAN
);
CREATE INDEX idx_returns_order ON fact_returns (order_id);
CREATE INDEX idx_returns_reason ON fact_returns (return_reason);

-- =============================================================================
-- FACT: fact_shipping
-- =============================================================================
CREATE TABLE fact_shipping (
    shipment_sk                    BIGSERIAL PRIMARY KEY,
    shipment_id                      VARCHAR(20) NOT NULL UNIQUE,
    order_id                           VARCHAR(20) NOT NULL REFERENCES fact_orders (order_id),
    carrier                               VARCHAR(40),
    ship_date                              DATE,
    delivery_date                            DATE,
    promised_delivery_days                     SMALLINT,
    actual_transit_days                          SMALLINT,
    is_delayed                                     BOOLEAN,
    shipping_cost                                    NUMERIC(8,2)
);
CREATE INDEX idx_shipping_order ON fact_shipping (order_id);
CREATE INDEX idx_shipping_delayed ON fact_shipping (is_delayed);

-- =============================================================================
-- FACT: fact_inventory  (periodic snapshot, grain: store x product)
-- =============================================================================
CREATE TABLE fact_inventory (
    inventory_sk                      BIGSERIAL PRIMARY KEY,
    store_id                            VARCHAR(20) NOT NULL REFERENCES dim_stores (store_id),
    product_id                            VARCHAR(20) NOT NULL REFERENCES dim_products (product_id),
    stock_on_hand                           INT,
    reorder_point                             INT,
    reorder_quantity                            INT,
    last_restocked_date                           DATE,
    stock_status                                    VARCHAR(20),
    UNIQUE (store_id, product_id)
);
CREATE INDEX idx_inventory_status ON fact_inventory (stock_status);
CREATE INDEX idx_inventory_product ON fact_inventory (product_id);

-- =============================================================================
-- FACT: fact_reviews
-- =============================================================================
CREATE TABLE fact_reviews (
    review_sk                        BIGSERIAL PRIMARY KEY,
    review_id                          VARCHAR(20) NOT NULL UNIQUE,
    product_id                           VARCHAR(20) NOT NULL REFERENCES dim_products (product_id),
    order_id                               VARCHAR(20) NOT NULL REFERENCES fact_orders (order_id),
    customer_id                              VARCHAR(20) NOT NULL REFERENCES dim_customers (customer_id),
    review_date                                DATE,
    rating                                        SMALLINT CHECK (rating BETWEEN 1 AND 5),
    sentiment                                       VARCHAR(20),
    verified_purchase                                 BOOLEAN,
    helpful_votes                                       INT
);
CREATE INDEX idx_reviews_product ON fact_reviews (product_id);
CREATE INDEX idx_reviews_rating ON fact_reviews (rating);

-- =============================================================================
-- FACT: fact_marketing_campaigns
-- =============================================================================
CREATE TABLE fact_marketing_campaigns (
    campaign_sk                       BIGSERIAL PRIMARY KEY,
    campaign_id                         VARCHAR(20) NOT NULL UNIQUE,
    campaign_name                         VARCHAR(150),
    campaign_type                           VARCHAR(40),
    channel                                   VARCHAR(40),
    target_country                              VARCHAR(60),
    start_date                                    DATE,
    end_date                                        DATE,
    budget_usd                                        NUMERIC(12,2),
    impressions                                         BIGINT,
    clicks                                                BIGINT,
    conversions                                             BIGINT,
    revenue_generated_usd                                     NUMERIC(12,2),
    ctr_pct                                                      NUMERIC(6,3),
    conversion_rate_pct                                            NUMERIC(6,3),
    roas                                                             NUMERIC(8,2)
);
CREATE INDEX idx_campaigns_channel ON fact_marketing_campaigns (channel);
CREATE INDEX idx_campaigns_dates ON fact_marketing_campaigns (start_date, end_date);

-- =============================================================================
-- FACT: fact_website_traffic  (grain: date x country)
-- =============================================================================
CREATE TABLE fact_website_traffic (
    traffic_sk                          BIGSERIAL PRIMARY KEY,
    traffic_date                          DATE NOT NULL,
    country                                 VARCHAR(60) NOT NULL,
    visitors                                  INT,
    sessions                                    INT,
    bounce_rate                                   NUMERIC(5,3),
    conversion_rate                                 NUMERIC(6,4),
    avg_session_duration_sec                          INT,
    UNIQUE (traffic_date, country)
);
CREATE INDEX idx_traffic_date ON fact_website_traffic (traffic_date);

-- =============================================================================
-- FACT: fact_weather  (grain: date x city)
-- =============================================================================
CREATE TABLE fact_weather (
    weather_sk                            BIGSERIAL PRIMARY KEY,
    weather_date                            DATE NOT NULL,
    country                                   VARCHAR(60),
    city                                        VARCHAR(60),
    temperature_c                                 NUMERIC(5,1),
    condition                                       VARCHAR(20),
    precipitation_mm                                  NUMERIC(6,1),
    UNIQUE (weather_date, city)
);
CREATE INDEX idx_weather_date ON fact_weather (weather_date);

-- =============================================================================
-- FACT: fact_economic_indicators  (grain: month x country)
-- =============================================================================
CREATE TABLE fact_economic_indicators (
    econ_sk                                BIGSERIAL PRIMARY KEY,
    indicator_month                          DATE NOT NULL,
    country                                    VARCHAR(60) NOT NULL,
    inflation_rate_pct                           NUMERIC(5,2),
    unemployment_rate_pct                          NUMERIC(5,2),
    consumer_confidence_index                        NUMERIC(6,1),
    gdp_growth_pct                                     NUMERIC(5,2),
    UNIQUE (indicator_month, country)
);

-- =============================================================================
-- TABLE & COLUMN COMMENTS (self-documenting schema)
-- =============================================================================
COMMENT ON TABLE fact_order_items IS 'Finest-grain sales fact: one row per product per order. Source of truth for revenue, margin, and basket analysis.';
COMMENT ON TABLE fact_orders IS 'Order-header fact: one row per order. total_amount is derived from fact_order_items at load time.';
COMMENT ON COLUMN dim_products.margin_pct IS 'Gross margin % = (unit_price - unit_cost) / unit_price * 100';
COMMENT ON TABLE fact_inventory IS 'Periodic snapshot fact (not transactional) — represents current stock state per store/product as of last ETL run.';
