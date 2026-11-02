-- ============================================================================
-- SkyPoints Loyalty Platform: Snowflake Raw Landing Layer DDL
-- Billions-scale daily ingestion for Flat File Profiles & JSON Redemptions
-- ============================================================================

-- 1. Create Schema and File Formats
CREATE SCHEMA IF NOT EXISTS SKYPOINTS_LAKE.RAW;
USE SCHEMA SKYPOINTS_LAKE.RAW;

-- File format for pipe-delimited member profile flat files
CREATE OR REPLACE FILE FORMAT FF_PIPE_DELIMITED
    TYPE = CSV
    FIELD_DELIMITER = '|'
    SKIP_HEADER = 0
    TRIM_SPACE = TRUE
    NULL_IF = ('', 'NULL', 'null')
    EMPTY_FIELD_AS_NULL = TRUE
    COMPRESSION = AUTO;

-- File format for semi-structured JSON redemption feed
CREATE OR REPLACE FILE FORMAT FF_JSON
    TYPE = JSON
    COMPRESSION = AUTO;

-- External stage pointing to partitioned cloud storage (S3 / Azure Blob / GCS)
-- Pattern: s3://skypoints-landing/feed_date=YYYYMMDD/
CREATE OR REPLACE STAGE STG_SKYPOINTS_LANDING
    FILE_FORMAT = FF_PIPE_DELIMITED;

-- 2. Raw Landing Table for Member Profiles (Transient, 1-day retention)
CREATE OR REPLACE TRANSIENT TABLE RAW_MEMBER_PROFILES (
    raw_record_id        NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    record_type          VARCHAR(1),        -- 'H' for header, 'D' for detail
    col_1_member_name    VARCHAR(255),
    col_2_member_id      VARCHAR(50),
    col_3_enroll_date    VARCHAR(50),
    col_4_flight_date    VARCHAR(50),
    col_5_tier_code      VARCHAR(20),
    col_6_agent_name     VARCHAR(255),
    col_7_state          VARCHAR(20),
    col_8_country        VARCHAR(50),
    col_9_dob            VARCHAR(50),
    col_10_is_active     VARCHAR(10),
    -- Audit and file lineage metadata
    file_name            VARCHAR(255) DEFAULT METADATA$FILENAME,
    file_row_number      NUMBER DEFAULT METADATA$FILE_ROW_NUMBER,
    ingestion_timestamp  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 3. Raw Landing Table for Semi-Structured JSON Redemptions
CREATE OR REPLACE TRANSIENT TABLE RAW_REDEMPTIONS (
    raw_redemption_id    NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    payload              VARIANT,           -- Full nested JSON payload
    file_name            VARCHAR(255) DEFAULT METADATA$FILENAME,
    file_row_number      NUMBER DEFAULT METADATA$FILE_ROW_NUMBER,
    ingestion_timestamp  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- 4. Quarantine / Dead-Letter Table for Corrupted Records
CREATE OR REPLACE TABLE QUARANTINE_MEMBERS (
    quarantine_id        NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    raw_record_id        NUMBER,
    member_id            VARCHAR(50),
    member_name          VARCHAR(255),
    error_code           VARCHAR(50),
    error_description    VARCHAR(500),
    raw_payload          VARCHAR(2000),
    quarantine_timestamp TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

