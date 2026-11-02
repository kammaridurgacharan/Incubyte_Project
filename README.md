# SkyPoints Global Airline Loyalty Data Platform

An end-to-end data engineering pipeline for **SkyPoints**, a global airline loyalty network. The system processes two high-volume daily feeds:
1. **Member Profiles** (pipe-delimited flat file): Passenger profile updates, enrollment dates, flight dates, tiers, and residency.
2. **Mileage Redemptions** (semi-structured JSON): Transactional partner airline mileage redemption events.

The platform provides data cleansing, schema drift protection, country-based table routing with cross-border relocation handling, semi-structured JSON flattening, and loyalty analytics.

---

## Architecture Overview

```
Daily Feeds (Profiles .dat + Redemptions .json)
       │
       ▼
[ Ingestion Layer ] ──► FlatFileParser & JsonRedemptionParser
       │                 (Dynamic header mapping, leading zero repair, type checks)
       ▼
[ Staging & DQ ]    ──► DataQualityValidator
       │                 • Derived Age (from DOB)
       │                 • Derived Stale_Member flag (days since flight > 90)
       │                 • Dead-letter quarantine for corrupt records
       ▼
[ Target Serving ]  ──► CountryRouter & Fact Loader
                         • Per-Country Tables (Table_India, Table_USA, Table_Canada, ...)
                         • Latest-Record-Wins relocation reconciliation
                         • FACT_REDEMPTIONS (Flattened JSON transactions)
                         • 360° Member Loyalty Summary View
```

* **Production Target**: Snowflake DDL and SQL scripts (`sql/snowflake/`) designed for multi-cluster warehouse scaling, automatic micro-partitioning, and native `VARIANT` JSON processing at billions-of-rows scale.
* **Local Engine**: Embedded DuckDB pipeline (`src/skypoints/pipeline.py`) that executes identical vectorized columnar SQL locally with zero cloud dependencies.

For detailed design decisions, trade-off analysis, and data issue remediation, see **[`docs/DESIGN.md`](docs/DESIGN.md)**.

---

## Key Features

* **Dynamic Schema Drift Protection**: Detects header variations at runtime and maps columns by name rather than hardcoded positional indices, preventing field shifts when schemas evolve.
* **Defensive Date & Key Handling**: Automatically restores leading zeros in dates dropped by upstream systems (`LPAD` on DOB) and enforces `Member_Id` as the unique surrogate business key with identity-conflict detection.
* **Country Routing & Relocation**: Splits members into country-specific tables (`Table_India`, `Table_USA`, etc.) while enforcing the "latest record wins" rule. When a member moves across borders, they are updated in the new country table and purged from the former.
* **Semi-Structured JSON Flattening**: Flattens nested redemption arrays into queryable fact rows and joins them back to member profiles for 360° loyalty metrics.
* **Non-Blocking Quarantine Engine**: Corrupt records are isolated into a dead-letter quarantine table with source line numbers and diagnostic error codes, keeping production batch pipelines running.

---

## Quick Start

### 1. Installation
```bash
# Clone the repository
git clone <repo-url>
cd skypoints-loyalty-platform

# Install development dependencies
pip install -e ".[dev]"
```

### 2. Run Automated Test Suite
```bash
# Run all 33 unit and integration tests
python -m pytest -v
```

### 3. Run Pipeline Demo
```bash
# Execute the live demonstration pipeline
python demo.py
```

The demo runs the complete pipeline against sample data, displaying:
1. Staging table derivations (`Age`, `Stale_Member` flag, days elapsed).
2. Country-specific target tables.
3. Flattened redemption transactions (`FACT_REDEMPTIONS`).
4. Analytical join view (lifetime miles, completed vs. pending miles, partner counts).
5. Cross-border member relocation (demonstrating atomic move from USA to India).
6. Data quality quarantine isolating intentionally corrupted records with line numbers.

---

## Repository Structure

```
├── demo.py                         # Standalone interactive pipeline demonstration
├── pyproject.toml                  # Package configuration & test dependencies
├── README.md                       # Main project documentation
├── docs/
│   └── DESIGN.md                   # Architecture choices, trade-offs, and scaling strategy
├── sql/
│   └── snowflake/                  # Production Snowflake DDL & ELT transformations
│       ├── 01_raw_landing.sql      # Raw tables, file formats, external stages, quarantine
│       ├── 02_staging.sql          # Staging table, Age & Stale derivations
│       ├── 03_country_targets.sql  # Per-country target tables (Table_India, Table_USA, etc.)
│       ├── 04_redemptions.sql      # JSON flattening and member loyalty join queries
│       └── 05_merge_transforms.sql # "Latest record wins" deduplication & cross-table MERGE
├── src/
│   └── skypoints/                  # Core Python data engineering package
│       ├── config.py               # Constants, ISO country mappings, tier definitions
│       ├── models.py               # Pydantic schemas (Raw, Staged, Flattened, Quarantine)
│       ├── pipeline.py             # End-to-end DuckDB-powered pipeline orchestrator
│       ├── ingestion/              # Flat-file and semi-structured JSON parsers
│       ├── transforms/             # Staging derivations & country router with relocation
│       └── quality/                # Schema constraints & dead-letter quarantine engine
├── tests/                          # 33 comprehensive pytest unit and integration tests
└── data/                           # Sample data fixtures & multi-day relocation feeds
```

---

## Production SQL Scripts

The `sql/snowflake/` directory contains production-ready Snowflake scripts:
* **`01_raw_landing.sql`**: Transient landing tables for flat files and raw JSON `VARIANT` payloads.
* **`02_staging.sql`**: Parameterized staging load with vectorized Age derivation and Stale Member evaluation.
* **`03_country_targets.sql`**: Clustered country-specific target tables plus an enterprise unified dimension (`DIM_MEMBERS`).
* **`04_redemptions.sql`**: Vectorized `LATERAL FLATTEN` queries and analytical summary views.
* **`05_merge_transforms.sql`**: Multi-table atomic `MERGE` statements enforcing "latest record wins" across country borders.
