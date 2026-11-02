"""End-to-end pipeline orchestrator for SkyPoints Loyalty Data Platform."""

from dataclasses import dataclass, field
from datetime import date
import re
from typing import Any, Dict, List, Optional
import uuid
import duckdb

from src.skypoints.config import DEFAULT_AS_OF_DATE
from src.skypoints.ingestion.flat_file_parser import FlatFileParser
from src.skypoints.ingestion.json_parser import JsonRedemptionParser
from src.skypoints.models import (
    FlattenedRedemptionRecord,
    QuarantineRecord,
    RawMemberRecord,
    StagingMemberRecord,
)
from src.skypoints.quality.validators import DataQualityValidator
from src.skypoints.transforms.country_router import CountryRouter
from src.skypoints.transforms.staging import StagingTransformer


@dataclass
class PipelineExecutionResult:
    """Encapsulates the output artifacts of an end-to-end pipeline run."""
    batch_id: str = ""
    raw_records_count: int = 0
    staged_records_count: int = 0
    quarantined_count: int = 0
    redemptions_count: int = 0
    staged_records: List[StagingMemberRecord] = field(default_factory=list)
    country_tables: Dict[str, List[StagingMemberRecord]] = field(default_factory=dict)
    quarantined_records: List[QuarantineRecord] = field(default_factory=list)
    redemption_records: List[FlattenedRedemptionRecord] = field(default_factory=list)
    analytical_summary: List[Dict[str, Any]] = field(default_factory=list)


class SkyPointsPipeline:
    """Orchestrates ingestion, staging derivations, quality validation, country routing, and joins."""

    def __init__(self, as_of_date: Optional[date] = None) -> None:
        self.as_of_date = as_of_date or DEFAULT_AS_OF_DATE
        self.flat_parser = FlatFileParser()
        self.json_parser = JsonRedemptionParser()
        self.transformer = StagingTransformer(as_of_date=self.as_of_date)
        self.validator = DataQualityValidator()
        self.router = CountryRouter()
        self.db = duckdb.connect(database=":memory:")
        self._init_duckdb_schema()

    def reset(self) -> None:
        """Resets database tables and in-memory router state for a fresh execution."""
        self.router.reset()
        for tbl in ["RAW_MEMBERS", "STAGING_MEMBERS", "FACT_REDEMPTIONS", "QUARANTINE_RECORDS"]:
            self.db.execute(f"DELETE FROM {tbl};")

    def _init_duckdb_schema(self) -> None:
        """Initializes relational tables in local DuckDB to match Snowflake DDL."""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS RAW_MEMBERS (
                member_name VARCHAR,
                member_id VARCHAR,
                enrollment_date VARCHAR,
                flight_date VARCHAR,
                tier_code VARCHAR,
                agent_name VARCHAR,
                state_code VARCHAR,
                country_code VARCHAR,
                dob VARCHAR,
                is_active VARCHAR,
                batch_id VARCHAR
            );
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS STAGING_MEMBERS (
                member_id VARCHAR,
                member_name VARCHAR,
                enrollment_date DATE,
                flight_date DATE,
                tier_code VARCHAR,
                agent_name VARCHAR,
                state_code VARCHAR,
                country_code VARCHAR,
                standardized_country VARCHAR,
                dob DATE,
                is_active VARCHAR,
                age INTEGER,
                stale_member BOOLEAN,
                days_since_last_flight INTEGER,
                batch_id VARCHAR
            );
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS FACT_REDEMPTIONS (
                txn_id VARCHAR,
                member_id VARCHAR,
                feed_date DATE,
                txn_date DATE,
                partner VARCHAR,
                miles_redeemed INTEGER,
                status VARCHAR,
                batch_id VARCHAR
            );
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS QUARANTINE_RECORDS (
                source_line_num INTEGER,
                error_code VARCHAR,
                error_message VARCHAR,
                raw_payload VARCHAR,
                batch_id VARCHAR
            );
        """)

    def run(
        self,
        flat_file_path: Optional[str] = None,
        flat_file_text: Optional[str] = None,
        json_file_path: Optional[str] = None,
        json_file_text: Optional[str] = None,
        batch_id: Optional[str] = None,
        reset_state: bool = False,
    ) -> PipelineExecutionResult:
        """Executes the complete ETL, validation, and country routing pipeline."""
        if reset_state:
            self.reset()

        active_batch_id = batch_id or f"batch_{uuid.uuid4().hex[:8]}"
        all_quarantine: List[QuarantineRecord] = []

        # 1. Ingestion: Member Profile Flat File
        raw_records: List[RawMemberRecord] = []
        if flat_file_path:
            _, raw_records, parse_errors = self.flat_parser.parse_file(flat_file_path)
            all_quarantine.extend(parse_errors)
        elif flat_file_text:
            _, raw_records, parse_errors = self.flat_parser.parse_text(flat_file_text)
            all_quarantine.extend(parse_errors)

        # 2. Ingestion: Semi-Structured JSON Redemptions
        redemption_records: List[FlattenedRedemptionRecord] = []
        if json_file_path:
            redemption_records, json_errors = self.json_parser.parse_file(json_file_path)
            all_quarantine.extend(json_errors)
        elif json_file_text:
            redemption_records, json_errors = self.json_parser.parse_text(json_file_text)
            all_quarantine.extend(json_errors)

        # 3. Staging Transformations (Age, Stale_Member, Country Standardization)
        staged_candidates: List[StagingMemberRecord] = []
        for raw in raw_records:
            staged, transform_err = self.transformer.transform(raw)
            if transform_err:
                all_quarantine.append(transform_err)
            elif staged:
                staged.batch_id = active_batch_id
                staged_candidates.append(staged)

        # 4. Data Quality Validation (Mandatory checks, Key Uniqueness, Chronology)
        valid_staged_records, validation_errs = self.validator.validate_batch(staged_candidates)
        all_quarantine.extend(validation_errs)

        # 5. Country Table Routing & 'Latest Record Wins' Relocation
        self.router.process_batch(valid_staged_records)

        # 6. Load into DuckDB Tables
        self._populate_duckdb(
            raw_records,
            valid_staged_records,
            redemption_records,
            all_quarantine,
            active_batch_id,
        )

        # 7. Execute Analytical SQL Join (Member Profile <-> Redemptions)
        summary_query = """
            SELECT 
                m.member_id,
                m.member_name,
                m.tier_code,
                m.standardized_country,
                m.age,
                m.stale_member,
                m.flight_date AS last_flight_date,
                CAST(COUNT(r.txn_id) AS INTEGER) AS total_transactions,
                CAST(COALESCE(SUM(r.miles_redeemed), 0) AS INTEGER) AS total_miles_redeemed,
                CAST(COALESCE(SUM(CASE WHEN r.status = 'COMPLETED' THEN r.miles_redeemed ELSE 0 END), 0) AS INTEGER) AS completed_miles,
                CAST(COALESCE(SUM(CASE WHEN r.status = 'PENDING' THEN r.miles_redeemed ELSE 0 END), 0) AS INTEGER) AS pending_miles,
                MAX(r.txn_date) AS latest_redemption_date,
                CAST(COUNT(DISTINCT r.partner) AS INTEGER) AS unique_partners
            FROM STAGING_MEMBERS m
            LEFT JOIN FACT_REDEMPTIONS r
                ON m.member_id = r.member_id
            GROUP BY 
                m.member_id, m.member_name, m.tier_code, m.standardized_country,
                m.age, m.stale_member, m.flight_date
            ORDER BY m.member_id;
        """
        cursor = self.db.execute(summary_query)
        columns = [desc[0] for desc in cursor.description]
        summary_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return PipelineExecutionResult(
            batch_id=active_batch_id,
            raw_records_count=len(raw_records),
            staged_records_count=len(valid_staged_records),
            quarantined_count=len(all_quarantine),
            redemptions_count=len(redemption_records),
            staged_records=valid_staged_records,
            country_tables=self.router.all_tables(),
            quarantined_records=all_quarantine,
            redemption_records=redemption_records,
            analytical_summary=summary_rows,
        )

    def _populate_duckdb(
        self,
        raw_records: List[RawMemberRecord],
        staged_records: List[StagingMemberRecord],
        redemptions: List[FlattenedRedemptionRecord],
        quarantine: List[QuarantineRecord],
        batch_id: str,
    ) -> None:
        """Loads processed entities into DuckDB tables for SQL querying."""
        # Insert raw members
        for r in raw_records:
            self.db.execute(
                """INSERT INTO RAW_MEMBERS VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    r.member_name,
                    r.member_id,
                    r.enrollment_date_raw,
                    r.flight_date_raw,
                    r.tier_code_raw,
                    r.agent_name_raw,
                    r.state_code_raw,
                    r.country_code_raw,
                    r.dob_raw,
                    r.is_active_raw,
                    batch_id,
                ],
            )

        # Insert staged members
        for s in staged_records:
            self.db.execute(
                """INSERT INTO STAGING_MEMBERS VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    s.member_id,
                    s.member_name,
                    s.enrollment_date,
                    s.flight_date,
                    s.tier_code,
                    s.agent_name,
                    s.state_code,
                    s.country_code,
                    s.standardized_country,
                    s.dob,
                    s.is_active,
                    s.age,
                    s.stale_member,
                    s.days_since_last_flight,
                    batch_id,
                ],
            )

        # Insert redemptions
        for red in redemptions:
            self.db.execute(
                """INSERT INTO FACT_REDEMPTIONS VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    red.txn_id,
                    red.member_id,
                    red.feed_date,
                    red.txn_date,
                    red.partner,
                    red.miles_redeemed,
                    red.status,
                    batch_id,
                ],
            )

        # Insert quarantine records
        for q in quarantine:
            self.db.execute(
                """INSERT INTO QUARANTINE_RECORDS VALUES (?, ?, ?, ?, ?)""",
                [q.source_line_num, q.error_code, q.error_message, q.raw_payload, batch_id],
            )

        # Populate per-country tables in DuckDB (sanitizing table names)
        for table_name, records in self.router.all_tables().items():
            clean_tbl = re.sub(r"[^A-Za-z0-9_]", "", table_name)
            if not clean_tbl:
                continue

            self.db.execute(
                f"CREATE TABLE IF NOT EXISTS {clean_tbl} AS SELECT * FROM STAGING_MEMBERS WHERE 1=0;"
            )
            self.db.execute(f"DELETE FROM {clean_tbl};")
            for rec in records:
                self.db.execute(
                    f"""INSERT INTO {clean_tbl} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        rec.member_id,
                        rec.member_name,
                        rec.enrollment_date,
                        rec.flight_date,
                        rec.tier_code,
                        rec.agent_name,
                        rec.state_code,
                        rec.country_code,
                        rec.standardized_country,
                        rec.dob,
                        rec.is_active,
                        rec.age,
                        rec.stale_member,
                        rec.days_since_last_flight,
                        batch_id,
                    ],
                )
