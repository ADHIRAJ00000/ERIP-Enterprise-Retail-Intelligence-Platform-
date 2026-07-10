-- =============================================================================
-- ERIP — dim_date population
-- Generates a full date dimension row for every day in the platform's range
-- using PostgreSQL's generate_series (no external load needed).
-- =============================================================================

INSERT INTO dim_date (
    date_sk, full_date, day_of_week, day_name, day_of_month, day_of_year,
    week_of_year, month_num, month_name, quarter, year, is_weekend,
    fiscal_year, fiscal_quarter
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT                          AS date_sk,
    d::DATE                                               AS full_date,
    EXTRACT(ISODOW FROM d)::SMALLINT                      AS day_of_week,
    TO_CHAR(d, 'Day')                                      AS day_name,
    EXTRACT(DAY FROM d)::SMALLINT                          AS day_of_month,
    EXTRACT(DOY FROM d)::SMALLINT                          AS day_of_year,
    EXTRACT(WEEK FROM d)::SMALLINT                         AS week_of_year,
    EXTRACT(MONTH FROM d)::SMALLINT                        AS month_num,
    TO_CHAR(d, 'Month')                                    AS month_name,
    EXTRACT(QUARTER FROM d)::SMALLINT                      AS quarter,
    EXTRACT(YEAR FROM d)::SMALLINT                         AS year,
    EXTRACT(ISODOW FROM d) IN (6, 7)                       AS is_weekend,
    -- Fiscal year assumed to start Feb 1 (common retail convention) — adjust as needed
    CASE WHEN EXTRACT(MONTH FROM d) >= 2
         THEN EXTRACT(YEAR FROM d)::SMALLINT
         ELSE EXTRACT(YEAR FROM d)::SMALLINT - 1 END        AS fiscal_year,
    CEIL(EXTRACT(MONTH FROM d) / 3.0)::SMALLINT              AS fiscal_quarter
FROM generate_series('2021-01-01'::DATE, '2025-12-31'::DATE, INTERVAL '1 day') AS d;
