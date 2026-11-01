"""Robust flat file parser for pipe-delimited member profile feeds."""

from typing import Dict, List, Optional, Tuple
from src.skypoints.config import EXPECTED_HEADER_COLUMNS
from src.skypoints.models import QuarantineRecord, RawMemberRecord


class FlatFileParser:
    """Parses pipe-delimited member profile feeds with header signature validation."""

    def __init__(self, delimiter: str = "|") -> None:
        self.delimiter = delimiter

    def parse_file(self, file_path: str) -> Tuple[List[str], List[RawMemberRecord], List[QuarantineRecord]]:
        """Parses a file from disk."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_text(content)

    def parse_text(self, content: str) -> Tuple[List[str], List[RawMemberRecord], List[QuarantineRecord]]:
        """Parses raw text content of the flat file."""
        lines = content.strip().splitlines()
        headers: List[str] = []
        records: List[RawMemberRecord] = []
        quarantine_errors: List[QuarantineRecord] = []
        header_map: Dict[str, int] = {}

        for line_num, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            # Strip outer pipes if present and split by delimiter
            parts = [p.strip() for p in line_str.split(self.delimiter)]
            # Filter leading/trailing empty string resulting from leading/trailing pipe
            if parts and parts[0] == "":
                parts.pop(0)
            if parts and parts[-1] == "":
                parts.pop(-1)

            if not parts:
                continue

            record_type = parts[0].upper()
            payload = parts[1:]

            if record_type == "H":
                headers = payload
                header_map = {col.lower(): idx for idx, col in enumerate(headers)}
                continue

            elif record_type == "D":
                # Detail record validation: ensure column count matches header if header was present
                expected_count = len(headers) if headers else len(EXPECTED_HEADER_COLUMNS)
                if len(payload) < expected_count:
                    quarantine_errors.append(
                        QuarantineRecord(
                            source_line_num=line_num,
                            raw_payload=line_str,
                            error_code="ERR_MALFORMED_DELIMITER_ROW",
                            error_message=f"Row has {len(payload)} fields, expected {expected_count}",
                        )
                    )
                    continue

                def get_field(col_name: str, fallback_idx: int) -> Optional[str]:
                    col_key = col_name.lower()
                    if col_key in header_map and header_map[col_key] < len(payload):
                        val = payload[header_map[col_key]]
                    elif fallback_idx < len(payload):
                        val = payload[fallback_idx]
                    else:
                        return None
                    return val if val != "" else None

                raw_rec = RawMemberRecord(
                    record_type="D",
                    member_name=get_field("member_name", 0),
                    member_id=get_field("member_id", 1),
                    enrollment_date_raw=get_field("enrollment_date", 2),
                    flight_date_raw=get_field("last_flight_date", 3),
                    tier_code_raw=get_field("tier_code", 4),
                    agent_name_raw=get_field("agent_name", 5),
                    state_code_raw=get_field("state", 6),
                    country_code_raw=get_field("country", 7),
                    dob_raw=get_field("dob", 8),
                    is_active_raw=get_field("is_active", 9),
                    source_line_num=line_num,
                )
                records.append(raw_rec)

            else:
                quarantine_errors.append(
                    QuarantineRecord(
                        source_line_num=line_num,
                        raw_payload=line_str,
                        error_code="ERR_UNKNOWN_RECORD_TYPE",
                        error_message=f"Unrecognized record type prefix: '{record_type}'",
                    )
                )

        return headers, records, quarantine_errors
