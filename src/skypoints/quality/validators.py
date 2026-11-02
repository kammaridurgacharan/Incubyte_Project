"""Data quality validation engine for member profile and transaction feeds."""

from datetime import date
from typing import Dict, List, Optional, Set, Tuple
from src.skypoints.config import VALID_ACTIVE_FLAGS, VALID_TIER_CODES
from src.skypoints.models import QuarantineRecord, StagingMemberRecord


class DataQualityValidator:
    """Enforces schema constraints, business rules, chronological consistency, and key uniqueness."""

    def __init__(
        self,
        allowed_tiers: Optional[Set[str]] = None,
        allowed_statuses: Optional[Set[str]] = None,
    ) -> None:
        self.allowed_tiers: Set[str] = allowed_tiers or VALID_TIER_CODES
        self.allowed_statuses: Set[str] = allowed_statuses or VALID_ACTIVE_FLAGS

    def validate_record(self, record: StagingMemberRecord) -> Tuple[bool, List[QuarantineRecord]]:
        """Validates a single staging member record against all business integrity rules."""
        errors: List[QuarantineRecord] = []
        line_num = record.source_line_num

        # 1. Mandatory field checks
        if not record.member_name or not record.member_name.strip():
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_MANDATORY_NULL",
                    error_message="Member_Name cannot be null or empty",
                )
            )

        if not record.member_id or not record.member_id.strip():
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_MANDATORY_NULL",
                    error_message="Member_Id cannot be null or empty",
                )
            )

        if not record.enrollment_date:
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_MANDATORY_NULL",
                    error_message="Enrollment_Date cannot be null or empty",
                )
            )

        # 2. Chronological integrity checks
        if record.enrollment_date and record.flight_date:
            if record.flight_date < record.enrollment_date:
                errors.append(
                    QuarantineRecord(
                        source_line_num=line_num,
                        raw_payload=str(record.model_dump()),
                        error_code="ERR_CHRONOLOGY_VIOLATION",
                        error_message=(
                            f"Flight date ({record.flight_date}) cannot be prior to "
                            f"enrollment date ({record.enrollment_date})"
                        ),
                    )
                )

        if record.dob and record.enrollment_date:
            if record.dob >= record.enrollment_date:
                errors.append(
                    QuarantineRecord(
                        source_line_num=line_num,
                        raw_payload=str(record.model_dump()),
                        error_code="ERR_INVALID_DOB_CHRONOLOGY",
                        error_message=(
                            f"Date of birth ({record.dob}) must precede "
                            f"enrollment date ({record.enrollment_date})"
                        ),
                    )
                )

        # 3. Domain and Enum Validations
        if record.tier_code and record.tier_code not in self.allowed_tiers:
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_INVALID_TIER",
                    error_message=f"Tier code '{record.tier_code}' is not recognized",
                )
            )

        if record.is_active and record.is_active not in self.allowed_statuses:
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_INVALID_STATUS",
                    error_message=f"Status code '{record.is_active}' is invalid (expected 'A' or 'I')",
                )
            )

        # 4. Biological sanity checks
        if record.age is not None and (record.age < 0 or record.age > 125):
            errors.append(
                QuarantineRecord(
                    source_line_num=line_num,
                    raw_payload=str(record.model_dump()),
                    error_code="ERR_BIOLOGICAL_SANITY",
                    error_message=f"Computed age {record.age} is outside valid human range (0-125)",
                )
            )

        return (len(errors) == 0, errors)

    def validate_batch(
        self, records: List[StagingMemberRecord]
    ) -> Tuple[List[StagingMemberRecord], List[QuarantineRecord]]:
        """Validates all records in batch, including primary key identity conflict detection."""
        all_quarantined: List[QuarantineRecord] = []

        # First pass: record-level validation
        pass_1_records: List[StagingMemberRecord] = []
        for rec in records:
            is_valid, errs = self.validate_record(rec)
            if is_valid:
                pass_1_records.append(rec)
            else:
                all_quarantined.extend(errs)

        # Second pass: Primary key conflict check
        # If the same Member_Id appears with DIFFERENT member names in the same feed,
        # flag as data corruption / identity conflict
        seen_names_for_id: Dict[str, Set[str]] = {}
        for rec in pass_1_records:
            mid = rec.member_id
            if mid not in seen_names_for_id:
                seen_names_for_id[mid] = set()
            seen_names_for_id[mid].add(rec.member_name.lower())

        conflicted_ids = {
            mid for mid, names in seen_names_for_id.items() if len(names) > 1
        }

        valid_records: List[StagingMemberRecord] = []
        for rec in pass_1_records:
            if rec.member_id in conflicted_ids:
                all_quarantined.append(
                    QuarantineRecord(
                        source_line_num=rec.source_line_num,
                        raw_payload=str(rec.model_dump()),
                        error_code="ERR_DUPLICATE_KEY_CONFLICT",
                        error_message=(
                            f"Member_Id '{rec.member_id}' is claimed by multiple distinct "
                            f"member names: {seen_names_for_id[rec.member_id]}"
                        ),
                    )
                )
            else:
                valid_records.append(rec)

        return valid_records, all_quarantined
