"""Country routing and 'Latest Record Wins' cross-table relocation manager."""

from datetime import date
import re
from typing import Dict, List, Optional, Tuple
from src.skypoints.config import COUNTRY_TABLE_MAPPING
from src.skypoints.models import StagingMemberRecord


class CountryRouter:
    """Manages country-specific target tables and enforces 'Latest Record Wins' across relocations."""

    def __init__(self) -> None:
        # Table name -> {member_id -> StagingMemberRecord}
        self.tables: Dict[str, Dict[str, StagingMemberRecord]] = {}
        # member_id -> (current_table_name, last_flight_date)
        self.member_locations: Dict[str, Tuple[str, Optional[date]]] = {}

    def reset(self) -> None:
        """Clears all router table states for clean batch reruns."""
        self.tables.clear()
        self.member_locations.clear()

    def get_table_name(self, record: StagingMemberRecord) -> str:
        """Determines sanitized target country table name for a record."""
        code_upper = (record.country_code or "UNKNOWN").strip().upper()
        if code_upper in COUNTRY_TABLE_MAPPING:
            raw_name = COUNTRY_TABLE_MAPPING[code_upper]
        elif record.standardized_country and record.standardized_country != "UNKNOWN":
            raw_name = f"Table_{record.standardized_country}"
        else:
            raw_name = "Table_Unknown"

        # Sanitize against SQL injection / illegal table identifier characters
        sanitized = re.sub(r"[^A-Za-z0-9_]", "", raw_name)
        return sanitized or "Table_Unknown"

    def deduplicate_batch(self, records: List[StagingMemberRecord]) -> List[StagingMemberRecord]:
        """Within-batch deduplication: keeps the latest flight date or latest processed timestamp."""
        best_per_member: Dict[str, StagingMemberRecord] = {}

        for rec in records:
            mid = rec.member_id
            if mid not in best_per_member:
                best_per_member[mid] = rec
                continue

            current = best_per_member[mid]
            rec_flight = rec.flight_date or date.min
            curr_flight = current.flight_date or date.min

            if rec_flight > curr_flight:
                best_per_member[mid] = rec
            elif rec_flight == curr_flight:
                if rec.processed_at >= current.processed_at:
                    best_per_member[mid] = rec

        return list(best_per_member.values())

    def process_batch(self, records: List[StagingMemberRecord]) -> None:
        """Ingests a batch of records, routes to country tables, and reconciles relocations."""
        deduped = self.deduplicate_batch(records)

        for rec in deduped:
            target_table = self.get_table_name(rec)
            mid = rec.member_id
            new_flight_date = rec.flight_date

            if mid in self.member_locations:
                prev_table, prev_flight_date = self.member_locations[mid]

                incoming_time = new_flight_date or date.min
                existing_time = prev_flight_date or date.min

                if incoming_time < existing_time:
                    # Stale / out-of-order record: ignore update
                    continue

                # Member relocated: remove from former table if country changed
                if prev_table != target_table and prev_table in self.tables:
                    self.tables[prev_table].pop(mid, None)

            # Insert or update in target country table
            if target_table not in self.tables:
                self.tables[target_table] = {}

            self.tables[target_table][mid] = rec
            self.member_locations[mid] = (target_table, new_flight_date)

    def get_table(self, table_name: str) -> List[StagingMemberRecord]:
        """Returns all records in a specific country table."""
        return list(self.tables.get(table_name, {}).values())

    def all_tables(self) -> Dict[str, List[StagingMemberRecord]]:
        """Returns all country tables and their records."""
        return {tbl: list(records.values()) for tbl, records in self.tables.items()}
