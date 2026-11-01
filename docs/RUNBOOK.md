# SkyPoints Live Demonstration Runbook & Interview Guide

This guide walks through running the live demonstration for Incubyte technical interviewers, explaining the key architecture points and answering common follow-up questions.

---

## 1. Quick Start Commands

### A. Run Full Test Suite (TDD Verification)
```powershell
python -m pytest
```
*Expected Result*: 26 passed tests covering unit, property, and end-to-end integration scenarios.

### B. Run Interactive Live Demonstration
```powershell
python demo.py
```
*Executes*:
1. Raw ingestion and staging derivations (`Age`, `Stale_Member > 90 days`).
2. Country table partitioning (`Table_India`, `Table_USA`, etc.).
3. Semi-structured JSON flattening (`FACT_REDEMPTIONS`).
4. Analytical join view (Member Profile $\leftrightarrow$ Redemption Fact).
5. "Latest Record Wins" relocation reconciliation across multiple days.
6. Dead-letter quarantine of corrupt sample records.

---

## 2. Key Discussion Topics for the Interview

### Topic 1: The Subtle Traps in the Sample Data
* **Trap A (Spec Drift)**: Position 9 was marked as `Post Code` in the legacy position table, but the operational file header (`|H|...`) and detail records actually carry `DOB`.
  * *Our Answer*: "We wrote a dynamic header-signature parser rather than hardcoding numeric index offsets. If the data team adds or rearranges fields, the parser adapts by name."
* **Trap B (Business Key Ambiguity)**: The legacy spec marked `Member Name` as the Key Column and `Member ID` as non-key.
  * *Our Answer*: "In airline systems, two people named 'John Smith' frequently enroll. `Member_Id` is the true surrogate business key. We enforce uniqueness and detect identity hijacking (same ID with differing names)."
* **Trap C (DOB Leading Zero Loss)**: Staging display showed `3051985` instead of `03051985`.
  * *Our Answer*: "Casting date strings directly to integer drops leading zeroes and corrupts months. We treat date components as strings with `LPAD(dob, 8, '0')` before date parsing."

### Topic 2: Scaling to Billions of Records Daily
* **Distributed Micro-Partitioning**:
  * Instead of looping in Python, ingestion uses cloud-native bulk COPY into Snowflake / Lakehouse.
  * Flat files arrive compressed in $100\text{MB}$ chunks (`.dat.gz`) to maximize read parallelism across compute nodes.
* **Idempotency & Replayability**:
  * Pipeline runs use deterministic date watermarks (`as_of_date`).
  * Deduplication uses windowing:
    ```sql
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY member_id 
        ORDER BY flight_date DESC, feed_timestamp DESC
    ) = 1
    ```
* **Unified Clustered Dimension vs Physical Table Sprawl**:
  * Maintaining 195 separate physical tables (`Table_India`, `Table_USA`, ...) creates DDL bloat and cross-table locking issues.
  * We implemented the required physical country tables, but also architected the enterprise solution: a unified `DIM_MEMBERS` clustered by `(Country, Member_Id)` with zero-copy secure views.

### Topic 3: Handling Cross-Country Relocations
* When member `223457` relocates from USA to India:
  * The pipeline executes an atomic cross-table reconciliation: upserting into `Table_India` and purging/deactivating from `Table_USA`.
  * Verified in `tests/test_country_router.py` and demonstrated in `demo.py`.

