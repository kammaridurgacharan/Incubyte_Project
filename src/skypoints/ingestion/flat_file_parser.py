"""Robust flat file parser for pipe-delimited member profile feeds."""

from typing import Dict, List, Optional, Set, Tuple
from src.skypoints.config import EXPECTED_HEADER_COLUMNS, LEGACY_SPEC_COLUMNS
from src.skypoints.models import QuarantineRecord, RawMemberRecord


class FlatFileParser:
    """Parses pipe-delimited member profile feeds with dynamic header mapping and schema drift detection."""

    def __init__(self, delimiter: str = "|") -> None:
        self.delimiter = delimiter
        self.detected_drifts: List[str] = []

    def parse_file(self, file_path: str) -> Tuple[List[str], List[RawMemberRecord], List[QuarantineRecord]]:
        """Parses a file from disk."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_text(content)

    def _extract_field(
        self,
        payload: List[str],
        header_map: Dict[str, int],
        col_name: str,
        fallback_idx: int,
    ) -> Optional[str]:
        """Extracts field value using dynamic header mapping or positional fallback."""
        col_key = col_name.lower()
        if col_key in header_map and header_map[col_key] < len(payload):
            val = payload[header_map[col_key]]
        elif fallback_idx < len(payload):
            val = payload[fallback_idx]
        else:
            return None
        return val if val != "" else None

    def _detect_drift(self, headers: List[str]) -> List[str]:
        """Compares discovered headers against specification contracts to detect schema drift."""
        drifts: List[str] = []
        found_set: Set[str] = {h.lower() for h in headers}

        # Check for columns documented in legacy spec but omitted from actual file (e.g. Post_Code)
        for expected in LEGACY_SPEC_COLUMNS:
            if expected.lower() not in found_set:
                drifts.append(f"Legacy spec column '{expected}' not present in operational feed header")

        # Check for new columns not in baseline expected list
        baseline_set = {h.lower() for h in EXPECTED_HEADER_COLUMNS}
        for h in headers:
            if h.lower() not in baseline_set:
                drifts.append(f"Discovered new/unmapped header column: '{h}'")

        return drifts

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

            parts = [p.strip() for p in line_str.split(self.delimiter)]
            # Drop empty boundary tokens caused by leading/trailing pipes
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
                self.detected_drifts = self._detect_drift(headers)
                continue

            elif record_type == "D":
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

                raw_rec = RawMemberRecord(
                    record_type="D",
                    member_name=self._extract_field(payload, header_map, "member_name", 0),
                    member_id=self._extract_field(payload, header_map, "member_id", 1),
                    enrollment_date_raw=self._extract_field(payload, header_map, "enrollment_date", 2),
                    flight_date_raw=self._extract_field(payload, header_map, "last_flight_date", 3),
                    tier_code_raw=self._extract_field(payload, header_map, "tier_code", 4),
                    agent_name_raw=self._extract_field(payload, header_map, "agent_name", 5),
                    state_code_raw=self._extract_field(payload, header_map, "state", 6),
                    country_code_raw=self._extract_field(payload, header_map, "country", 7),
                    dob_raw=self._extract_field(payload, header_map, "dob", 8),
                    is_active_raw=self._extract_field(payload, header_map, "is_active", 9),
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
