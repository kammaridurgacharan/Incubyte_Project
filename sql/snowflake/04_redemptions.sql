-- ============================================================================
-- SkyPoints Loyalty Platform: Semi-Structured JSON Redemption Flattening & Joins
-- Flattens redemptions JSON array and joins to Member Profiles
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS SKYPOINTS_LAKE.ANALYTICS;
USE SCHEMA SKYPOINTS_LAKE.ANALYTICS;

-- 1. Flattened Fact Table for Redemption Transactions
CREATE OR REPLACE TABLE FACT_REDEMPTIONS (
    redemption_key       VARCHAR(64) NOT NULL,
    txn_id               VARCHAR(50) NOT NULL,
    member_id            VARCHAR(18) NOT NULL,
    feed_date            DATE NOT NULL,
    txn_date             DATE NOT NULL,
    partner_name         VARCHAR(100) NOT NULL,
    miles_redeemed       NUMBER(12, 0) NOT NULL,
    txn_status           VARCHAR(20) NOT NULL,
    ingestion_timestamp  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (txn_id)
)
CLUSTER BY (txn_date, member_id);

-- 2. Vectorized JSON Flattening Query (Snowflake LATERAL FLATTEN)
INSERT INTO FACT_REDEMPTIONS (
    redemption_key,
    txn_id,
    member_id,
    feed_date,
    txn_date,
    partner_name,
    miles_redeemed,
    txn_status
)
SELECT
    MD5(CONCAT(f.value:txn_id::STRING, '|', r.payload:member_id::STRING)) AS redemption_key,
    TRIM(f.value:txn_id::STRING)                                          AS txn_id,
    TRIM(r.payload:member_id::STRING)                                     AS member_id,
    TRY_TO_DATE(r.payload:feed_date::STRING, 'YYYYMMDD')                  AS feed_date,
    TRY_TO_DATE(f.value:txn_date::STRING, 'YYYYMMDD')                     AS txn_date,
    TRIM(f.value:partner::STRING)                                          AS partner_name,
    f.value:miles_redeemed::NUMBER                                         AS miles_redeemed,
    UPPER(TRIM(f.value:status::STRING))                                    AS txn_status
FROM SKYPOINTS_LAKE.RAW.RAW_REDEMPTIONS r,
LATERAL FLATTEN(input => r.payload:redemptions) f
WHERE f.value:txn_id IS NOT NULL
  AND f.value:miles_redeemed::NUMBER >= 0;

-- 3. Analytical Joins: Joining Redemptions back to Member Profiles
-- View A: Comprehensive 360-Degree Member Loyalty Summary View
CREATE OR REPLACE VIEW V_MEMBER_REDEMPTION_SUMMARY AS
SELECT
    m.member_id,
    m.member_name,
    m.tier_code,
    m.standardized_country,
    m.age,
    m.stale_member,
    m.flight_date AS last_flight_date,
    COUNT(r.txn_id)                                         AS total_transactions,
    COALESCE(SUM(r.miles_redeemed), 0)                      AS total_miles_redeemed,
    COALESCE(SUM(CASE WHEN r.txn_status = 'COMPLETED' 
                      THEN r.miles_redeemed ELSE 0 END), 0) AS completed_miles,
    COALESCE(SUM(CASE WHEN r.txn_status = 'PENDING' 
                      THEN r.miles_redeemed ELSE 0 END), 0) AS pending_miles,
    MAX(r.txn_date)                                         AS latest_redemption_date,
    COUNT(DISTINCT r.partner_name)                          AS unique_partners_used
FROM SKYPOINTS_LAKE.STAGING.STAGING_MEMBERS m
LEFT JOIN FACT_REDEMPTIONS r
    ON m.member_id = r.member_id
GROUP BY ALL;

-- View B: Cross-Join to Specific Country Table (e.g. Table_India) for Active Partner Audits
CREATE OR REPLACE VIEW V_INDIA_ACTIVE_REDEMPTIONS AS
SELECT
    ind.member_id,
    ind.member_name,
    ind.tier_code,
    ind.state_code,
    r.txn_id,
    r.txn_date,
    r.partner_name,
    r.miles_redeemed,
    r.txn_status
FROM SKYPOINTS_LAKE.TARGETS.TABLE_INDIA ind
INNER JOIN FACT_REDEMPTIONS r
    ON ind.member_id = r.member_id
WHERE r.txn_status = 'COMPLETED';
