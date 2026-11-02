-- ============================================================================
-- SkyPoints Loyalty Platform: Country Routing & Latest-Record-Wins Relocation
-- Routes members to Table_<Country> handling cross-border member relocation
-- ============================================================================

USE SCHEMA SKYPOINTS_LAKE.TARGETS;

-- Step 1: Deduplicate Staging Feed ("Latest Record Wins")
-- When multiple updates exist for a member within the daily batch,
-- order by flight_date DESC and source file order to select the canonical row.
CREATE OR REPLACE TEMPORARY VIEW V_DEDUPED_STAGING AS
SELECT *
FROM SKYPOINTS_LAKE.STAGING.STAGING_MEMBERS
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY member_id 
    ORDER BY flight_date DESC NULLS LAST, processed_at DESC
) = 1;

-- ============================================================================
-- Pattern 1: Per-Country MERGE Statements & Relocation Reconciliation
-- When Member moves (e.g. USA -> India):
-- 1. Upsert into Table_India with latest details
-- 2. Purge stale record from previous country table
-- ============================================================================

-- 1. Upsert India Members
MERGE INTO TABLE_INDIA tgt
USING (SELECT * FROM V_DEDUPED_STAGING WHERE standardized_country = 'India') src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code, standardized_country,
        dob, is_active, age, stale_member, days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code, src.standardized_country,
        src.dob, src.is_active, src.age, src.stale_member, src.days_since_last_flight, CURRENT_TIMESTAMP()
    );

-- 2. Upsert USA Members
MERGE INTO TABLE_USA tgt
USING (SELECT * FROM V_DEDUPED_STAGING WHERE standardized_country = 'USA') src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code, standardized_country,
        dob, is_active, age, stale_member, days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code, src.standardized_country,
        src.dob, src.is_active, src.age, src.stale_member, src.days_since_last_flight, CURRENT_TIMESTAMP()
    );

-- 3. Upsert Canada Members
MERGE INTO TABLE_CANADA tgt
USING (SELECT * FROM V_DEDUPED_STAGING WHERE standardized_country = 'Canada') src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code, standardized_country,
        dob, is_active, age, stale_member, days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code, src.standardized_country,
        src.dob, src.is_active, src.age, src.stale_member, src.days_since_last_flight, CURRENT_TIMESTAMP()
    );

-- 4. Upsert Australia Members
MERGE INTO TABLE_AUSTRALIA tgt
USING (SELECT * FROM V_DEDUPED_STAGING WHERE standardized_country = 'Australia') src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code, standardized_country,
        dob, is_active, age, stale_member, days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code, src.standardized_country,
        src.dob, src.is_active, src.age, src.stale_member, src.days_since_last_flight, CURRENT_TIMESTAMP()
    );

-- 5. Upsert Philippines Members
MERGE INTO TABLE_PHILIPPINES tgt
USING (SELECT * FROM V_DEDUPED_STAGING WHERE standardized_country = 'Philippines') src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code, standardized_country,
        dob, is_active, age, stale_member, days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code, src.standardized_country,
        src.dob, src.is_active, src.age, src.stale_member, src.days_since_last_flight, CURRENT_TIMESTAMP()
    );

-- Cross-Country Relocation Cleanups:
-- Remove members from previous tables when their newest record belongs to another country:
DELETE FROM TABLE_USA WHERE member_id IN (SELECT member_id FROM V_DEDUPED_STAGING WHERE standardized_country <> 'USA');
DELETE FROM TABLE_INDIA WHERE member_id IN (SELECT member_id FROM V_DEDUPED_STAGING WHERE standardized_country <> 'India');
DELETE FROM TABLE_CANADA WHERE member_id IN (SELECT member_id FROM V_DEDUPED_STAGING WHERE standardized_country <> 'Canada');
DELETE FROM TABLE_AUSTRALIA WHERE member_id IN (SELECT member_id FROM V_DEDUPED_STAGING WHERE standardized_country <> 'Australia');
DELETE FROM TABLE_PHILIPPINES WHERE member_id IN (SELECT member_id FROM V_DEDUPED_STAGING WHERE standardized_country <> 'Philippines');

-- ============================================================================
-- Pattern 2: Enterprise Unified MERGE (Scale to Billions)
-- Zero cross-table delete complexity: Single atomic MERGE on DIM_MEMBERS
-- Automatically updates country partition in one I/O pass!
-- ============================================================================

MERGE INTO DIM_MEMBERS tgt
USING V_DEDUPED_STAGING src
ON tgt.member_id = src.member_id
WHEN MATCHED AND (src.flight_date >= tgt.last_flight_date OR tgt.last_flight_date IS NULL) THEN
    UPDATE SET
        tgt.member_name             = src.member_name,
        tgt.enrollment_date         = src.enrollment_date,
        tgt.last_flight_date        = src.flight_date,
        tgt.tier_code               = src.tier_code,
        tgt.agent_name              = src.agent_name,
        tgt.state_code              = src.state_code,
        tgt.raw_country_code        = src.raw_country_code,
        tgt.standardized_country    = src.standardized_country,
        tgt.dob                     = src.dob,
        tgt.is_active               = src.is_active,
        tgt.age                     = src.age,
        tgt.stale_member            = src.stale_member,
        tgt.days_since_last_flight  = src.days_since_last_flight,
        tgt.last_updated_at         = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
    INSERT (
        member_id, member_name, enrollment_date, last_flight_date,
        tier_code, agent_name, state_code, raw_country_code,
        standardized_country, dob, is_active, age, stale_member,
        days_since_last_flight, last_updated_at
    ) VALUES (
        src.member_id, src.member_name, src.enrollment_date, src.flight_date,
        src.tier_code, src.agent_name, src.state_code, src.raw_country_code,
        src.standardized_country, src.dob, src.is_active, src.age, src.stale_member,
        src.days_since_last_flight, CURRENT_TIMESTAMP()
    );
