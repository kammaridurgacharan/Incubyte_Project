# SkyPoints Global Airline Loyalty Data Engineering Platform
> **Incubyte Data Engineer Technical Assessment**  
> *Crafted with Test-Driven Development (TDD), Enterprise Scalability Design, and Software Craftsmanship.*

---

## 1. Executive Summary

This repository delivers a production-grade data engineering pipeline for **SkyPoints**, a global airline loyalty program. It processes two daily feeds at enterprise scale:
1. **Member Profile Feed**: High-volume pipe-delimited flat files (`|H|...` and `|D|...`).
2. **Mileage Redemption Feed**: Semi-structured JSON arrays capturing partner airline redemptions.

The solution satisfies all 6 assessment deliverables, resolves the discrepancies and anomalies in the sample data, and provides both **cloud-native Snowflake DDL/SQL** and a **runnable local pipeline with DuckDB** for live interview demonstrations.

---

## 2. Deliverables Checklist

| Deliverable | Requirement | Location in Codebase |
| :--- | :--- | :--- |
| **Deliverable 1** | Table queries (DDL) for Raw landing, Staging, and Country target tables in Snowflake. | [`sql/snowflake/01_raw_landing.sql`](sql/snowflake/01_raw_landing.sql)<br>[`sql/snowflake/02_staging.sql`](sql/snowflake/02_staging.sql)<br>[`sql/snowflake/03_country_targets.sql`](sql/snowflake/03_country_targets.sql) |
| **Deliverable 2** | Load Staging table with derived columns: `Age` (from DOB) and `Stale_Member` flag (`days since Flight_Date > 90`). | [`src/skypoints/transforms/staging.py`](src/skypoints/transforms/staging.py)<br>[`sql/snowflake/02_staging.sql`](sql/snowflake/02_staging.sql) |
| **Deliverable 3** | Transformation logic to split members into per-country target tables with the "latest record wins" rule for relocations. | [`src/skypoints/transforms/country_router.py`](src/skypoints/transforms/country_router.py)<br>[`sql/snowflake/05_merge_transforms.sql`](sql/snowflake/05_merge_transforms.sql) |
| **Deliverable 4** | Parse semi-structured JSON redemption feed into a flattened table and join back to member profile data. | [`src/skypoints/ingestion/json_parser.py`](src/skypoints/ingestion/json_parser.py)<br>[`sql/snowflake/04_redemptions.sql`](sql/snowflake/04_redemptions.sql) |
| **Deliverable 5** | Data validations: mandatory fields, key uniqueness, chronological checks, and catching sample anomalies. | [`src/skypoints/quality/validators.py`](src/skypoints/quality/validators.py)<br>[`tests/test_validators.py`](tests/test_validators.py) |
| **Deliverable 6** | Interactive live demonstration ready for technical interview pairing. | [`demo.py`](demo.py)<br>[`docs/RUNBOOK.md`](docs/RUNBOOK.md) |

---

## 3. High-Volume Architecture: Scaling to Billions of Records Daily

The pipeline was engineered around the constraint: *"Create the process considering we are getting billions of records every day."*

Detailed architectural analysis is documented in [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) and [`docs/ARCHITECTURE_DECISIONS_AND_DATA_STRATEGY.md`](docs/ARCHITECTURE_DECISIONS_AND_DATA_STRATEGY.md). Key design pillars include:

1. **Chunked, Splittable Object Storage**:
   * Daily feeds arrive pre-partitioned in $100\text{MB}$ compressed blocks (`part-*.dat.gz` and `part-*.json.gz`).
   * Avoids the single-file decompression bottleneck and allows parallel virtual warehouse clusters to ingest millions of rows/sec.
2. **Vectorized ELT (Pushdown Compute)**:
   * Heavy computations (Age calculation, Stale Member evaluation, JSON array unnesting) are executed in columnar SQL via Snowflake micro-partitions or DuckDB columnar vectors.
3. **Idempotent "Latest Record Wins" Relocation**:
   * Window function deduplication:
     $$\text{ROW\_NUMBER}() \text{ OVER (PARTITION BY member\_id ORDER BY flight\_date DESC, processed\_at DESC)} = 1$$
   * Cross-table reconciliation: When a member moves from USA to India, they are upserted into `Table_India` and deleted/deactivated in `Table_USA` atomically.
   * Scalable Alternative: A unified `DIM_MEMBERS` dimension clustered by `(Country, Member_Id)` with zero-maintenance country views.
4. **Dead-Letter Quarantine**:
   * Corrupt lines never crash the pipeline; they are isolated into `QUARANTINE_RECORDS` with explicit diagnostic error codes (`ERR_MANDATORY_NULL`, `ERR_CHRONOLOGY_VIOLATION`, `ERR_INVALID_TIER`) and source file line numbers preserved.

---

## 4. Anomalies & Traps Discovered in the Sample Data

| Identified Anomaly | Root Cause & Real-World Impact | Pipeline Resolution |
| :--- | :--- | :--- |
| **Spec Table vs File Header Drift** | Spec listed `Post Code` at position 9. Actual file header and rows omit `Post Code` and place `DOB` at position 9. | Parser validates header signatures dynamically by column name, preventing field misalignment. |
| **Key Column Misconfiguration** | Spec marked `Member Name` as Key Column (Y) and `Member ID` as non-key (N). | In airline loyalty systems, names are not unique. The pipeline enforces `Member_Id` as the primary key and validates against duplicate ID identity conflicts. |
| **DOB Leading Zero Truncation** | Sample flat file shows `03051985`, but Staging table preview showed `3051985`. | Integer casting drops the leading `0` (corrupting March `03` into `3`). Parser preserves string representation and applies `LPAD(dob, 8, '0')`. |
| **Country Code Inconsistency** | Mix of Alpha-3 (`USA`, `IND`, `CAN`), Alpha-2 (`AU`), and non-standard (`PHIL`). | ISO standardization dictionary normalizes all variations before routing to target tables (`Table_Australia`, `Table_Philippines`). |
| **Chronological Validity** | Flight before enrollment, or DOB after enrollment. | Quarantine validator isolates chronological paradoxes into the dead-letter queue. |

---

## 5. Getting Started & Live Demonstration

### Quick Setup
```bash
# Clone the repository and navigate into it
git clone <repo-url>
cd Incubyte_Project

# Install development dependencies
pip install -e ".[dev]"

# Run all 33 automated test suites (TDD verification)
python -m pytest

# Run the interactive live interview demonstration
python demo.py
```

### Live Demonstration Output Preview
Running `python demo.py` demonstrates:
1. **Staging Derivation**: Deriving `Age` (38) and `Stale_Member` (TRUE, 4111 days elapsed) from sample feeds.
2. **Country Target Tables**: Segregating members into `Table_India`, `Table_USA`, `Table_Canada`, `Table_Australia`, and `Table_Philippines`.
3. **Flattened JSON Redemptions**: Exploding nested redemptions into `FACT_REDEMPTIONS`.
4. **360-Degree Analytical Join**: Calculating completed miles, pending miles, and transaction counts per member.
5. **Live Relocation Reconciliation**: Moving Elena from USA to India and demonstrating automatic purge from `Table_USA`.
6. **Data Quality Quarantine**: Intercepting and quarantining corrupted test records with exact source line numbers.

---

## 6. Project Structure

```
Incubyte_Project/
├── demo.py                         # Interactive live interview demonstration runner
├── pyproject.toml                  # Python package configuration & test dependencies
├── README.md                       # Comprehensive project documentation
├── docs/
│   ├── ARCHITECTURE_DECISIONS_AND_DATA_STRATEGY.md # Comprehensive ADR, warehouse trade-offs, and anomaly resolution
│   ├── SYSTEM_DESIGN.md            # Billions-scale architectural design & trade-offs
│   ├── DATA_DICTIONARY.md          # Schema specifications & data anomaly analysis
│   └── RUNBOOK.md                  # Step-by-step interview guide for live demonstration
├── sql/
│   └── snowflake/                  # Production Snowflake DDL & ELT transformations
│       ├── 01_raw_landing.sql      # Raw tables, file formats, external stages, quarantine
│       ├── 02_staging.sql          # Staging table, Age & Stale derivations
│       ├── 03_country_targets.sql  # Per-country target tables (Table_India, Table_USA, etc.)
│       ├── 04_redemptions.sql      # JSON flattening and member loyalty join queries
│       └── 05_merge_transforms.sql # "Latest record wins" deduplication & cross-table MERGE
├── src/
│   └── skypoints/                  # Modular Python data engineering package
│       ├── config.py               # Constants, ISO country mappings, tier definitions
│       ├── models.py               # Pydantic schemas (Raw, Staged, Flattened, Quarantine)
│       ├── pipeline.py             # End-to-end DuckDB-powered orchestrator
│       ├── ingestion/              # Delimiter & semi-structured JSON parsers
│       ├── transforms/             # Staging derivations & country router with relocation
│       └── quality/                # Schema constraints & dead-letter quarantine engine
├── tests/                          # 33 comprehensive pytest unit and integration tests
└── data/                           # Real problem sample fixtures & relocation test data
```

---

## 7. Git Commit History (Evolution of Solution)

The Git history records each phase of TDD evolution:
* `chore`: Project scaffolding, configuration, and data fixtures.
* `docs`: System design for billions-scale architecture and data dictionary.
* `sql`: Snowflake DDL for raw landing, staging, targets, and redemptions.
* `feat(ingestion)`: Flat-file parser with header detection and zero preservation.
* `feat(ingestion)`: Semi-structured JSON redemption flattener with validation.
* `feat(transforms)`: Staging transformations for Age, Stale_Member, and country normalization.
* `feat(transforms)`: Country router with latest-record-wins relocation manager.
* `feat(quality)`: Data quality engine with key uniqueness and dead-letter quarantine.
* `feat(pipeline)`: End-to-end pipeline orchestrator with DuckDB analytical queries.
* `feat(demo)`: Interactive live demonstration CLI runner (`demo.py`) and interview runbook.
* `refactor`: Audit remediation, line number provenance, negative miles checks, and production SQL alignment.
