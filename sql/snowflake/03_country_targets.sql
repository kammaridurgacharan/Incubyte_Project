-- ============================================================================
-- SkyPoints Loyalty Platform: Country-Specific Target Tables DDL
-- Deliverable 1: Target tables for India, USA, Canada, Australia, Philippines
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS SKYPOINTS_LAKE.TARGETS;
USE SCHEMA SKYPOINTS_LAKE.TARGETS;

-- Common Target Table Structure Template
-- Pattern: TABLE_<CountryName> clustered by (MEMBER_ID) for high-performance point lookups

-- 1. Table for India Members
CREATE OR REPLACE TABLE TABLE_INDIA (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) DEFAULT 'IND',
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

-- 2. Table for USA Members
CREATE OR REPLACE TABLE TABLE_USA (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) DEFAULT 'USA',
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

-- 3. Table for Canada Members
CREATE OR REPLACE TABLE TABLE_CANADA (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) DEFAULT 'CAN',
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

-- 4. Table for Australia Members
CREATE OR REPLACE TABLE TABLE_AUSTRALIA (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) DEFAULT 'AUS',
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

-- 5. Table for Philippines Members
CREATE OR REPLACE TABLE TABLE_PHILIPPINES (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) DEFAULT 'PHL',
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (member_id);

-- ============================================================================
-- Enterprise Alternative: Unified Clustered Dimension (Scale to Billions)
-- Avoids DDL explosion for 195+ countries while offering zero-copy country views
-- ============================================================================
CREATE OR REPLACE TABLE DIM_MEMBERS (
    member_id               VARCHAR(18) NOT NULL,
    member_name             VARCHAR(255) NOT NULL,
    enrollment_date         DATE NOT NULL,
    last_flight_date        DATE,
    tier_code               VARCHAR(5),
    agent_name              VARCHAR(255),
    state_code              VARCHAR(5),
    country_code            VARCHAR(10) NOT NULL,
    standardized_country    VARCHAR(50) NOT NULL,
    dob                     DATE,
    is_active               VARCHAR(1) DEFAULT 'A',
    age                     NUMBER(3, 0),
    stale_member            BOOLEAN,
    last_updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (member_id)
)
CLUSTER BY (standardized_country, member_id);

-- Zero-overhead views on top of clustered dimension:
CREATE OR REPLACE VIEW VIEW_TABLE_INDIA AS
SELECT * FROM DIM_MEMBERS WHERE standardized_country = 'India';

CREATE OR REPLACE VIEW VIEW_TABLE_USA AS
SELECT * FROM DIM_MEMBERS WHERE standardized_country = 'USA';
