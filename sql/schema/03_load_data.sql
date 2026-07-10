-- =============================================================================
-- ERIP — Data Load Script
-- Loads all generated CSVs into the star schema using psql's \copy
-- (client-side, so no server filesystem permissions needed).
--
-- Run with:
--   psql -h localhost -U erip_user -d erip_dw -f sql/schema/03_load_data.sql
--
-- Note: CSVs are gzip-compressed (data/raw/*.csv.gz). \copy cannot read
-- gzip directly, so either:
--   (a) decompress first:  gunzip -k data/raw/*.csv.gz
--   (b) or pipe through a program copy: \copy ... FROM PROGRAM 'gunzip -c data/raw/dim_customers.csv.gz'
-- This script uses option (b) for a zero-extra-disk-space load.
-- =============================================================================


-- Load order matters: dimensions before facts that reference them.

\copy dim_suppliers (supplier_id, supplier_name, country, reliability_score, avg_lead_time_days, contract_start_date, is_active) FROM PROGRAM 'gunzip -c data/raw/dim_suppliers.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_customers (customer_id, first_name, last_name, email, gender, age, country, city, currency, signup_date, acquisition_channel, customer_segment, is_loyalty_member, marketing_opt_in) FROM PROGRAM 'gunzip -c data/raw/dim_customers.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_products (product_id, product_name, category, subcategory, brand, unit_price, unit_cost, weight_kg, launch_date, is_discontinued, rating_avg, supplier_id, margin_pct) FROM PROGRAM 'gunzip -c data/raw/dim_products.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_stores (store_id, store_name, store_type, country, city, square_footage, opened_date, is_active, manager_employee_id) FROM PROGRAM 'gunzip -c data/raw/dim_stores.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_employees (employee_id, first_name, last_name, role, store_id, hire_date, annual_salary_usd, performance_rating, is_active) FROM PROGRAM 'gunzip -c data/raw/dim_employees.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_coupons (coupon_id, coupon_code, discount_type, discount_value, issue_date, expiry_date, min_purchase_amount, times_redeemed, is_active) FROM PROGRAM 'gunzip -c data/raw/dim_coupons.csv.gz' WITH (FORMAT csv, HEADER true)

\copy dim_holiday_calendar (holiday_date, holiday_name, is_major_shopping_event) FROM PROGRAM 'gunzip -c data/raw/dim_holiday_calendar.csv.gz' WITH (FORMAT csv, HEADER true)

-- Facts
\copy fact_orders (order_id, customer_id, store_id, order_date, channel, order_status, payment_method, total_amount) FROM PROGRAM 'gunzip -c data/raw/fact_orders.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_order_items (order_item_id, order_id, order_date, product_id, quantity, unit_price, discount_pct, line_revenue, line_cost, line_profit) FROM PROGRAM 'gunzip -c data/raw/fact_order_items.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_payments (payment_id, order_id, payment_date, amount, payment_method, payment_status, transaction_fee_pct) FROM PROGRAM 'gunzip -c data/raw/fact_payments.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_returns (return_id, order_id, order_item_id, return_date, return_reason, refund_amount, restocked) FROM PROGRAM 'gunzip -c data/raw/fact_returns.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_shipping (shipment_id, order_id, carrier, ship_date, delivery_date, promised_delivery_days, actual_transit_days, is_delayed, shipping_cost) FROM PROGRAM 'gunzip -c data/raw/fact_shipping.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_inventory (store_id, product_id, stock_on_hand, reorder_point, reorder_quantity, last_restocked_date, stock_status) FROM PROGRAM 'gunzip -c data/raw/fact_inventory.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_reviews (review_id, product_id, order_id, customer_id, review_date, rating, sentiment, verified_purchase, helpful_votes) FROM PROGRAM 'gunzip -c data/raw/fact_reviews.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_marketing_campaigns (campaign_id, campaign_name, campaign_type, channel, target_country, start_date, end_date, budget_usd, impressions, clicks, conversions, revenue_generated_usd, ctr_pct, conversion_rate_pct, roas) FROM PROGRAM 'gunzip -c data/raw/fact_marketing_campaigns.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_website_traffic (traffic_date, country, visitors, sessions, bounce_rate, conversion_rate, avg_session_duration_sec) FROM PROGRAM 'gunzip -c data/raw/fact_website_traffic.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_weather (weather_date, country, city, temperature_c, condition, precipitation_mm) FROM PROGRAM 'gunzip -c data/raw/fact_weather.csv.gz' WITH (FORMAT csv, HEADER true)

\copy fact_economic_indicators (indicator_month, country, inflation_rate_pct, unemployment_rate_pct, consumer_confidence_index, gdp_growth_pct) FROM PROGRAM 'gunzip -c data/raw/fact_economic_indicators.csv.gz' WITH (FORMAT csv, HEADER true)

-- Refresh planner statistics after bulk load
ANALYZE;

SELECT 'Load complete' AS status,
       (SELECT COUNT(*) FROM fact_orders) AS orders,
       (SELECT COUNT(*) FROM fact_order_items) AS order_items,
       (SELECT COUNT(*) FROM dim_customers) AS customers;
