# SkyPoints Architecture Decisions, Data Strategy & Anomaly Resolution

> **System Architecture & Design Rationale**  
> **Author:** Durga Charan  
> **Project:** SkyPoints Global Airline Loyalty Data Engineering Platform  

---

## 1. Engineering Philosophy & Core Design Principles

Building a data engineering platform for a global loyalty program with millions of members and high-volume daily feeds requires balancing three core priorities:
1. **Software Craftsmanship & Test-Driven Development (TDD)**: The business logic (such as member routing, deduplication, and age calculations) must be modular, deterministic, and protected by comprehensive unit and integration tests.
2. **Defensive Ingestion**: Real-world vendor feeds are rarely pristine. Upstream source systems drift from specifications, drop leading zeros, send conflicting keys, or deliver records out of order. A resilient ingestion engine isolates bad data without terminating entire batch pipelines.
3. **Decoupled Architecture for Scale**: The system is designed so that local execution (for development, testing, and interview demonstration) requires zero cloud infrastructure, while the production design maps directly to distributed columnar storage (Snowflake / Lakehouse) capable of processing billions of records daily.

---

## 2. Technology Selection & Warehouse Evaluation: Why We Chose What We Chose

The assessment requires DDL and transformation logic for landing, staging, and country targets (e.g., Snowflake), while considering a daily volume of billions of records.

### Warehouse Architecture Evaluation

| Capability / Factor | Snowflake (Production Design) | Databricks (Delta / PySpark) | DuckDB (Local Pipeline Engine) | Traditional RDBMS (e.g., Postgres) |
| :--- | :--- | :--- | :--- | :--- |
| **Ingestion at Scale (Billions/day)** | **High**: Native `COPY INTO` with file-level parallelism; multi-cluster autoscaling warehouses. | **High**: PySpark Auto Loader streaming over object storage. Excellent for heavy streaming. | **High (Local)**: Vectorized C++ execution; handles millions in-memory without server overhead. | **Poor**: Single-node I/O bottleneck; row-locking contention on concurrent bulk writes. |
| **Semi-Structured JSON Handling** | **Native**: `VARIANT` type with direct path queries (`payload:redemptions`) and vectorized `LATERAL FLATTEN`. | **High**: `from_json()` and `explode()` on struct schemas. | **Native**: Direct JSON array `unnest()` and JSON querying. | **Moderate**: `JSONB` with GIN indexing, but high write overhead at scale. |
| **Micro-Partitioning & Pruning** | **Automatic**: 50–500MB micro-partitions with min/max clustering keys (`CLUSTER BY`). | Requires explicit partition columns and Liquid Clustering / Z-Ordering. | In-memory columnar scanning with partition pushdown. | Manual declarative partitioning (`PARTITION BY LIST/RANGE`). |
| **Storage & Compute Decoupling** | **Full**: Storage on cloud object store; compute warehouses auto-suspend when idle. | **Full**: Storage on Delta Lake; compute on ephemeral Databricks clusters. | **Embedded**: In-process engine running directly inside the pipeline process. | **Coupled**: Storage and compute bound to the same database instance. |
| **Operational & Demo Feasibility** | Enterprise cloud standard; requires cloud credentials and active billing. | Requires JVM, Spark cluster runtime, and metastore configuration. | **Zero External Infrastructure**: Runs in-process, instant startup, 100% ANSI SQL standard. | Heavy server setup; lacks columnar analytical speed for window functions. |

### Why Snowflake for Cloud Production
1. **Zero-Maintenance Micro-Partitioning**: Snowflake automatically organizes tables into micro-partitions ($50\text{--}500\text{ MB}$ uncompressed). At high volumes, queries filtering by `member_id` or `flight_date` prune out 99% of micro-partitions via min/max metadata, avoiding expensive full table scans.
2. **Vectorized VARIANT Processing**: Snowflake stores semi-structured data columnarly behind the scenes. Vectorized queries using `LATERAL FLATTEN` run across billions of rows in native C++ compute without row-by-row deserialization overhead.
3. **Decoupled Workloads**: Bulk daily loads run on an isolated ingestion warehouse (`LOAD_WH`) that scales out during morning batch windows and immediately suspends, avoiding compute contention with analytical workloads (`ANALYTICS_WH`).

### Why DuckDB for Local Demonstration & Development
* **Exact Parity with Analytical SQL**: DuckDB implements vectorized columnar query execution, ANSI window functions (`QUALIFY`, `ROW_NUMBER()`), and JSON array unnesting matching Snowflake's semantics.
* **Frictionless Collaboration**: Anyone running the project needs only Python and `pip install duckdb`. The entire 33-test suite executes in **1.6 seconds** on a standard developer machine, providing instant feedback without mock database servers.

---

## 3. Data Volume Strategy: Processing Billions of Records Daily

### Throughput & Storage Sizing
* **Daily Volume**: $1,000,000,000\text{ records/day}$
* **Throughput Required**:
  * Steady-state rate: $\approx 11,574\text{ rows/second}$
  * 2-Hour Batch Window rate: $\approx 138,888\text{ rows/second}$
* **Payload Footprint**:
  * Member Profile (10 columns, $\approx 150\text{ bytes/row}$): $\approx 150\text{ GB/day}$ raw ($\approx 35\text{ GB}$ compressed).
  * Redemptions (JSON, $\approx 250\text{ bytes/member}$): $\approx 250\text{ GB/day}$ raw ($\approx 50\text{ GB}$ compressed).

### Scalable Ingestion Architecture

```
[Source Feeds] 
       │
       ▼ (Pre-chunked 100MB-250MB compressed parts)
[Cloud Object Store: S3 / GCS / Azure Blob]
       │
       ▼ (Parallel COPY INTO / Snowpipe)
[RAW_MEMBER_PROFILES / RAW_REDEMPTIONS] (Transient / 1-day retention)
       │
       ▼ (Vectorized ELT & Quality Quarantine)
[STAGING_MEMBERS] ─── (QUALIFY ROW_NUMBER() Deduplication)
       │
       ├──► [TABLE_INDIA, TABLE_USA, TABLE_CANADA, etc.] (Country-Specific)
       └──► [DIM_MEMBERS] (Unified Clustered Dimension)
```

1. **Pre-Chunked Splittable Files**: Feeds arrive split into $100\text{MB}$ to $250\text{MB}$ compressed blocks (`part-00000.dat.gz` through `part-01500.dat.gz`). This allows distributed warehouse nodes to decompress and ingest files in parallel.
2. **Vectorized Pushdown ELT**: Calculations for `Age` and `Stale_Member` are executed in-database via columnar SQL expressions rather than pulling billions of rows into Python application memory.
3. **Colocated Fact/Dimension Joins**: Both `FACT_REDEMPTIONS` and `DIM_MEMBERS` are clustered by `member_id`, enabling bucket-level merge joins that eliminate cross-node network shuffling.

---

## 4. Anomaly Catalogue & Resolution Blueprint

The sample dataset in the problem statement contains several deliberate, real-world data discrepancies. Here is how our architecture addresses each one:

### 1. Schema Drift: Spec Table vs. Operational File Header
* **Issue**: The legacy specification table listed 11 positions with `Post Code` at position 9. However, the operational flat file header (`|H|...`) and detail records (`|D|...`) completely omit `Post Code` and place `DOB` at position 9 and `Is_Active` at position 10.
* **Risk**: Positional index parsers (`row[8]` = Post Code, `row[9]` = DOB) read `DOB` as an integer Post Code and `Is_Active` as a date, breaking ingestion.
* **Resolution**: `FlatFileParser` inspects the header row at runtime, constructs a column-to-index mapping, and binds fields by column name. It also logs detected drift when operational headers differ from baseline contracts.

### 2. Business Key Ambiguity: Member Name vs. Member ID
* **Issue**: The specification table marked `Member Name` as `Key Column: Y` and `Member ID` as `Key Column: N`.
* **Risk**: Two passengers named "Elena" or "Ravi" would overwrite each other's records if `Member Name` were used as the primary key.
* **Resolution**:
  * Enforced `Member_Id` as the unique surrogate business key.
  * Added identity conflict detection in `DataQualityValidator`: if the same `Member_Id` appears with conflicting member names within a batch, both rows are quarantined (`ERR_DUPLICATE_KEY_CONFLICT`).

### 3. Date Corruption: Truncation of Leading Zero in DOB
* **Issue**: In the sample flat file, Elena's DOB is `03051985`. In the sample staging preview, it appears as `3051985` (7 digits), caused by numeric conversion dropping the leading zero.
* **Risk**: Calling standard date parsers on `3051985` fails because the month string is malformed.
* **Resolution**: In both SQL and Python, 7-digit DOB strings are automatically restored with `LPAD(dob, 8, '0')` before parsing as `MMDDYYYY`.

### 4. Country Code Heterogeneity
* **Issue**: The feed contains a mix of 3-letter ISO Alpha-3 (`USA`, `IND`, `CAN`), 2-letter ISO Alpha-2 (`AU`), and informal abbreviations (`PHIL`).
* **Risk**: Blind table naming produces fragmented tables (`Table_PHIL` vs `Table_PHL` vs `Table_Philippines`).
* **Resolution**: A canonical lookup dictionary standardizes all known country abbreviations to consistent target tables (`Table_Philippines`, `Table_Australia`).

### 5. Member Relocation & "Latest Record Wins"
* **Issue**: When a member relocates from one country to another (e.g. Elena moves from USA to India), an update must insert into `Table_India` and purge the stale record from `Table_USA`.
* **Resolution**:
  * Within-batch deduplication via windowing:
    $$\text{ROW\_NUMBER}() \text{ OVER (PARTITION BY member\_id ORDER BY flight\_date DESC, feed_date DESC)} = 1$$
  * Cross-table reconciliation: `CountryRouter` and SQL MERGE scripts check the member's existing country location. If the new record is more recent, it upserts into the new country table and removes the member from the prior table.

### 6. Missing Optional Fields & Delimiter Shift
* **Issue**: When optional fields (like `Agent_Name`) are empty, naive parsers that strip empty tokens shift subsequent columns to the left.
* **Resolution**: The parser counts delimiter positions explicitly, converting empty delimited tokens (`||`) into `None`/`NULL` without shifting columns.

### 7. Chronological Integrity
* **Issue**: Flights recorded prior to enrollment dates, or birthdates recorded after enrollment.
* **Resolution**: `DataQualityValidator` enforces chronological sanity (`flight_date >= enrollment_date` and `dob < enrollment_date`), routing violations to `QUARANTINE_RECORDS` with source line numbers preserved.

---

## 5. Schema Governance & Future-Proofing

### Ingestion vs. Serving Governance

```
Landing Layer (Schema-on-Read)
  - Raw string columns & JSON VARIANT payloads.
  - Accommodates new upstream vendor attributes without pipeline failure.
        │
        ▼
Staging Layer (Strict Schema Enforcement)
  - Type casting & validation rules (DATE, INTEGER).
  - Non-null constraints on business keys.
  - Dead-letter quarantine for malformed records.
        │
        ▼
Serving Layer (Contract-Bound Target Tables)
  - Stable consumer interfaces (Country Tables / Clustered Dimension).
  - Versioned analytical views.
```

### Handling Future Schema Changes in Production
1. **Additive Changes (Backward-Compatible)**:
   * If source systems add a column (e.g., `Lounge_Access_Tier`):
     * The landing layer absorbs it dynamically via `VARIANT` or Snowflake `INFER_SCHEMA`.
     * An `ALTER TABLE ADD COLUMN` migration is applied to staging and target tables.
     * Historical partitions default to `NULL` without requiring table rewrites.
2. **Breaking Changes (Incompatible)**:
   * If a mandatory column is renamed (e.g., `Member_Id` $\to$ `Customer_Id`):
     * The header validation step catches the missing key at the batch boundary.
     * The batch is quarantined and an operational alert is emitted with the diff of expected vs. received column names.
3. **Data Contracts**:
   * Implementing JSON Schema contracts for partner feeds and Great Expectations / Soda checks at the staging boundary prevents breaking downstream analytics.

---

## 6. Fault Tolerance, Idempotency & Dead-Letter Quarantine

### Pipeline Idempotency Invariants
* **Replay Safety**: Running the pipeline multiple times over the same input feed produces the exact same row counts and table states.
* **Deterministic Metrics**: All date calculations accept an `as_of_date` parameter (default: `2024-01-15`), ensuring that historical backfills and test runs yield deterministic outputs regardless of execution date.
* **Batch Lineage**: Every execution generates a unique `batch_id`, allowing auditing and surgical rollbacks.

### Dead-Letter Queue (DLQ) / Quarantine Strategy
Rather than silently dropping corrupt rows (`ON ERROR = CONTINUE`) or crashing the entire batch on a single bad row (`FAIL FAST`), bad records are isolated into `QUARANTINE_RECORDS`:
* `source_line_num`: Line number in source file.
* `raw_payload`: Unaltered source text.
* `error_code`: Structured code (`ERR_MANDATORY_NULL`, `ERR_CHRONOLOGY_VIOLATION`, `ERR_INVALID_TIER`).
* `error_message`: Remediation diagnostic.

Valid records continue through staging and target loading uninterrupted.
