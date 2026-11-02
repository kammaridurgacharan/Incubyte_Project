# SkyPoints Data Platform — Design & Architecture

A concise overview of the technical decisions, architecture, data quality handling, and scalability considerations for the SkyPoints loyalty data pipeline.

---

## 1. System Overview

SkyPoints receives two daily feeds:
1. **Member Profiles** (pipe-delimited flat file): Profile data, tiers, enrollment dates, flight dates, and country.
2. **Mileage Redemptions** (semi-structured JSON): Partner airline redemption transactions per member.

The pipeline ingests both feeds, derives business attributes (`Age` from DOB, `Stale_Member` if days since last flight > 90), handles cross-border member moves, flattens redemptions, and joins transactions to member profiles.

```
[Raw Feeds]
    │
    ├── Member Profiles (.dat) ──► FlatFileParser ──► Staging & Quality Checks ──► Country Tables
    │                                                                                (India, USA, etc.)
    │
    └── Redemptions (.json)   ──► JsonParser     ──► FACT_REDEMPTIONS ───────────► Analytical Join
```

---

## 2. Technology Choices & Trade-Offs

### Production Warehouse: Snowflake
* **Why Snowflake**:
  * **Native VARIANT & LATERAL FLATTEN**: Parses and unnests JSON redemption arrays in vectorized C++ compute without serde bottlenecks.
  * **Automatic Micro-Partitioning**: Columns are automatically divided into 50–500MB micro-partitions. Clustering on `(member_id, flight_date)` prunes out 99% of data scans without manual partition maintenance.
  * **Decoupled Storage & Compute**: Heavy daily loads run on an isolated auto-scaling ingestion warehouse that spins down to zero cost when idle, preventing resource contention with analyst queries.
* **Trade-Offs**:
  * *vs. Databricks/Spark*: Spark is excellent for unstructured streaming and ML, but adds unnecessary cluster management complexity for batch tabular/JSON pipelines.
  * *vs. Traditional RDBMS (Postgres)*: Row-level locking and single-node writes become severe bottlenecks at hundreds of gigabytes per day.

### Local Execution & CI: DuckDB
* **Why DuckDB**:
  * Runs embedded in-process (`pip install duckdb`) with zero external infrastructure, credentials, or cloud costs.
  * Executes vectorized columnar SQL matching Snowflake syntax (window functions, `QUALIFY`, `ROW_NUMBER()`, and JSON unnesting).
  * Runs the full 33-test suite in **~1 second**.

---

## 3. Handling Messy Data & Edge Cases

Real-world feeds often drift from specification documents. The pipeline guards against several specific anomalies:

| Anomaly in Feed | Why It Breaks Naive Code | How We Handle It |
| :--- | :--- | :--- |
| **Spec Drift (Missing Column)** | Legacy spec listed `Post Code` at col 9, but actual file has `DOB` at col 9 and no Post Code. Fixed-index reading (`row[8]`) corrupts dates. | `FlatFileParser` inspects the `\|H\|` header dynamically and maps fields by column name, ignoring index shifts. |
| **Key Column Confusion** | Legacy doc marked Member Name as primary key. Names collide frequently in loyalty programs. | Enforced `Member_Id` as unique business key. Added identity conflict check: if same ID arrives with different names, both are quarantined. |
| **DOB Leading Zero Loss** | Upstream systems convert `03051985` to integer `3051985`, dropping the leading zero and breaking date parsers. | Restored using `LPAD(dob, 8, '0')` before casting to `DATE`. |
| **Country Code Inconsistency** | Feeds mix 3-letter (`USA`, `IND`), 2-letter (`AU`), and non-standard strings (`PHIL`). | Standardized via lookup map (`PHIL` $\to$ `Philippines`, `AU` $\to$ `Australia`). |
| **Member Relocations** | Elena moves from USA to India. A simple insert into `Table_India` leaves stale duplicate data in `Table_USA`. | Applied "latest record wins": `ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY flight_date DESC)`. The pipeline upserts into the new country table and deletes/deactivates from the old one. |
| **Missing Optional Fields** | Empty `Agent_Name` can cause naive splitters to shift subsequent columns to the left. | Explicit delimiter counting treats `\|\|` as `None`/`NULL` without column shifting. |
| **Chronological Inconsistencies** | Flights logged before enrollment date, or birthdates recorded after enrollment. | Caught by `DataQualityValidator` and routed to `QUARANTINE_RECORDS` with source line numbers preserved. |
| **Corrupt / Negative Miles** | Vendor sends negative redemption miles or malformed status. | Validated in `JsonRedemptionParser`; bad records quarantined while valid records proceed. |

---

## 4. Scaling to Billions of Records Daily

At $1\text{B}$ records/day ($\approx 150\text{--}250\text{ GB}$ compressed/day):

1. **Pre-Chunked Splittable Files**: Files arrive split into $100\text{MB}-250\text{MB}$ parts (`part-*.dat.gz`), allowing distributed warehouse nodes to load concurrently.
2. **Pushdown ELT**: Transformations (`Age`, `Stale_Member > 90 days`, and JSON flattening) run in-database using set-based SQL rather than pulling billions of rows into Python memory.
3. **Idempotent Reruns**: Deduplication uses window functions (`QUALIFY ROW_NUMBER() = 1`) and a deterministic `as_of_date` parameter, ensuring backfills produce identical results.
4. **Unified Clustered Dimension**: To avoid managing 195 separate physical country tables in production, we provide an enterprise alternative: a single `DIM_MEMBERS` table clustered by `(standardized_country, member_id)` with zero-copy views per country (`VIEW_TABLE_INDIA`).

---

## 5. Schema Reference

### Member Profiles (Staging)
* `member_id` (VARCHAR, PK) — Unique member identifier.
* `member_name` (VARCHAR) — Full name.
* `enrollment_date` (DATE) — Loyalty enrollment date (`YYYY-MM-DD`).
* `flight_date` (DATE) — Last flight completed (`YYYY-MM-DD`).
* `tier_code` (VARCHAR) — Tier status (`GLD`, `SLV`, `PLT`, `BRZ`, `BLU`).
* `agent_name` (VARCHAR) — Servicing agent (optional).
* `state_code` (VARCHAR) — State/province abbreviation.
* `country_code` (VARCHAR) — Raw country code.
* `standardized_country` (VARCHAR) — Canonical country name used for routing.
* `dob` (DATE) — Date of birth (`YYYY-MM-DD`).
* `is_active` (CHAR) — Member status (`A` = Active, `I` = Inactive).
* `age` (INTEGER) — Derived completed years from DOB.
* `stale_member` (BOOLEAN) — Derived flag (`True` if days since last flight > 90).
* `days_since_last_flight` (INTEGER) — Days elapsed since `flight_date`.

### Redemptions (Flattened Fact)
* `txn_id` (VARCHAR, PK) — Unique transaction identifier.
* `member_id` (VARCHAR, FK) — Joins to Staging / Country Tables.
* `feed_date` (DATE) — Feed generation date.
* `txn_date` (DATE) — Redemption transaction date.
* `partner` (VARCHAR) — Partner airline or service name.
* `miles_redeemed` (INTEGER) — Positive mileage amount.
* `status` (VARCHAR) — `COMPLETED`, `PENDING`, `CANCELLED`, `FAILED`.

