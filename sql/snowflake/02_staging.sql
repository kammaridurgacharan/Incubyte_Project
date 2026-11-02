-- ============================================================================
-- SkyPoints Loyalty Platform: Staging Layer DDL & Derived Transformations
-- Deliverable 2: Compute Age from DOB and Stale_Member flag (>90 days)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS SKYPOINTS_LAKE.STAGING;
USE SCHEMA SKYPOINTS_LAKE.STAGING;

-- Benchmark As-Of Date parameter for reproducible batch backfills (can be set per run)
SET AS_OF_DATE = '2024-01-15'::DATE;

-- 1. Staging Table DDL with Typed Columns & Audit Attributes
CREATE OR REPLACE TABLE STAGING_MEMBERS (
    staging_id              NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    flight_date             DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    raw_country_code        VARCHAR(10),
    standardized_country    VARCHAR(50) NOT NULL,
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    
    -- Derived Business Metrics
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    days_since_last_flight  NUMBER,
    
    -- Pipeline Lineage
    batch_id                VARCHAR(50),
    source_file             VARCHAR(255),
    source_row_num          NUMBER,
    processed_at            TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 2. Staging Load Transformation from Raw (Vectorized ELT Query)
-- Handles leading zero in DOB, parses YYYYMMDD dates, computes Age and Stale flag.
INSERT INTO STAGING_MEMBERS (
    member_id,
    member_name,
    enrollment_date,
    flight_date,
    tier_code,
    agent_name,
    state_code,
    raw_country_code,
    standardized_country,
    dob,
    is_active,
    age,
    stale_member,
    days_since_last_flight,
    source_file,
    source_row_num
)
WITH parsed_source AS (
    SELECT
        col_2_member_id                                         AS raw_member_id,
        col_1_member_name                                       AS raw_member_name,
        TRY_TO_DATE(col_3_enroll_date, 'YYYYMMDD')              AS clean_enroll_date,
        TRY_TO_DATE(col_4_flight_date, 'YYYYMMDD')              AS clean_flight_date,
        UPPER(TRIM(col_5_tier_code))                            AS clean_tier_code,
        NULLIF(TRIM(col_6_agent_name), '')                      AS clean_agent_name,
        UPPER(TRIM(col_7_state))                                AS clean_state,
        UPPER(TRIM(col_8_country))                              AS clean_country,
        -- Preserve leading zero in DOB (8 chars: MMDDYYYY or DDMMYYYY)
        TRY_TO_DATE(LPAD(TRIM(col_9_dob), 8, '0'), 'MMDDYYYY')   AS clean_dob,
        COALESCE(UPPER(TRIM(col_10_is_active)), 'A')            AS clean_is_active,
        file_name,
        file_row_number
    FROM SKYPOINTS_LAKE.RAW.RAW_MEMBER_PROFILES
    WHERE record_type = 'D'
      AND col_2_member_id IS NOT NULL
      AND col_1_member_name IS NOT NULL
),
standardized AS (
    SELECT
        raw_member_id,
        raw_member_name,
        clean_enroll_date,
        clean_flight_date,
        clean_tier_code,
        clean_agent_name,
        clean_state,
        clean_country,
        -- Country code standardization: handle 2-letter, 3-letter, and non-standard strings
        CASE clean_country
            WHEN 'USA'  THEN 'USA'
            WHEN 'US'   THEN 'USA'
            WHEN 'IND'  THEN 'India'
            WHEN 'IN'   THEN 'India'
            WHEN 'CAN'  THEN 'Canada'
            WHEN 'CA'   THEN 'Canada'
            WHEN 'AU'   THEN 'Australia'
            WHEN 'AUS'  THEN 'Australia'
            WHEN 'PHIL' THEN 'Philippines'
            WHEN 'PHL'  THEN 'Philippines'
            WHEN 'PH'   THEN 'Philippines'
            ELSE COALESCE(clean_country, 'UNKNOWN')
        END AS canonical_country,
        clean_dob,
        clean_is_active,
        -- Accurate age derivation accounting for leap years and birth month/day
        CASE 
            WHEN clean_dob IS NOT NULL THEN
                DATEDIFF(year, clean_dob, $AS_OF_DATE) - 
                IFF(DATEADD(year, DATEDIFF(year, clean_dob, $AS_OF_DATE), clean_dob) > $AS_OF_DATE, 1, 0)
            ELSE NULL 
        END AS computed_age,
        -- Stale Member Flag: days since last flight > 90 relative to batch benchmark date
        CASE
            WHEN clean_flight_date IS NULL THEN TRUE
            WHEN DATEDIFF(day, clean_flight_date, $AS_OF_DATE) > 90 THEN TRUE
            ELSE FALSE
        END AS is_stale_member,
        DATEDIFF(day, clean_flight_date, $AS_OF_DATE) AS days_elapsed,
        file_name,
        file_row_number
    FROM parsed_source
)
SELECT
    raw_member_id,
    raw_member_name,
    clean_enroll_date,
    clean_flight_date,
    clean_tier_code,
    clean_agent_name,
    clean_state,
    clean_country,
    canonical_country,
    clean_dob,
    clean_is_active,
    computed_age,
    is_stale_member,
    days_elapsed,
    file_name,
    file_row_number
FROM standardized;
