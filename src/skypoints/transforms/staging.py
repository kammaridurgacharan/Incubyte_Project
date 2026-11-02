"""Staging transformation logic: Age calculation, Stale_Member flag, and country standardization."""

from datetime import date, datetime
from typing import Optional, Tuple
from src.skypoints.config import (
    COUNTRY_TABLE_MAPPING,
    DEFAULT_AS_OF_DATE,
    STALE_MEMBER_THRESHOLD_DAYS,
)
from src.skypoints.models import QuarantineRecord, RawMemberRecord, StagingMemberRecord


class StagingTransformer:
    """Transforms raw parsed member rows into clean, enriched staging records."""

    def __init__(self, as_of_date: Optional[date] = None) -> None:
        self.as_of_date: date = as_of_date or DEFAULT_AS_OF_DATE

    def parse_date(self, date_str: Optional[str], is_dob: bool = False) -> Optional[date]:
        """Parses date string with leading zero preservation and multi-format support.
        
        DOB Interpretation:
        In US/global airline passenger data (like the sample), DOB '03051985' represents March 5, 1985 (MMDDYYYY).
        When leading zeroes are dropped by upstream numeric conversion (e.g. '3051985'), LPAD restores '03051985'.
        Fallback orders: MMDDYYYY -> YYYYMMDD -> DDMMYYYY.
        """
        if not date_str or not str(date_str).strip():
            return None

        clean_str = str(date_str).strip()

        if is_dob:
            # Restore dropped leading zero (e.g., '3051985' -> '03051985')
            if len(clean_str) == 7:
                clean_str = "0" + clean_str

            for fmt in ("%m%d%Y", "%Y%m%d", "%d%m%Y"):
                try:
                    return datetime.strptime(clean_str, fmt).date()
                except ValueError:
                    continue
            return None

        # Standard flight and enrollment date format: YYYYMMDD
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(clean_str, fmt).date()
            except ValueError:
                continue
        return None

    def compute_age(self, dob: Optional[date]) -> Optional[int]:
        """Calculates completed years of age as of the pipeline reference date."""
        if not dob:
            return None
        has_had_birthday = (self.as_of_date.month, self.as_of_date.day) >= (dob.month, dob.day)
        return self.as_of_date.year - dob.year - (0 if has_had_birthday else 1)

    def compute_stale_status(self, flight_date: Optional[date]) -> Tuple[bool, Optional[int]]:
        """Determines if member is stale based on days since last flight (> 90 days)."""
        if flight_date is None:
            return True, None
        delta_days = (self.as_of_date - flight_date).days
        is_stale = delta_days > STALE_MEMBER_THRESHOLD_DAYS
        return is_stale, delta_days

    def standardize_country(self, country_code: Optional[str]) -> str:
        """Maps diverse country string representations (AU, PHIL, IND, USA) to standard names."""
        if not country_code or not str(country_code).strip():
            return "UNKNOWN"
        code_upper = str(country_code).strip().upper()
        table_name = COUNTRY_TABLE_MAPPING.get(code_upper)
        if table_name:
            return table_name.replace("Table_", "")
        return code_upper

    def transform(
        self, raw: RawMemberRecord
    ) -> Tuple[Optional[StagingMemberRecord], Optional[QuarantineRecord]]:
        """Enriches raw member row with typed dates, Age, Stale flag, and country."""
        if not raw.member_id or not raw.member_name or not raw.enrollment_date_raw:
            return None, QuarantineRecord(
                source_line_num=raw.source_line_num,
                raw_payload=str(raw.model_dump()),
                error_code="ERR_MANDATORY_NULL",
                error_message="Missing mandatory field (Member_Name, Member_Id, or Enrollment_Date)",
            )

        enroll_dt = self.parse_date(raw.enrollment_date_raw)
        if not enroll_dt:
            return None, QuarantineRecord(
                source_line_num=raw.source_line_num,
                raw_payload=str(raw.model_dump()),
                error_code="ERR_INVALID_ENROLLMENT_DATE",
                error_message=f"Cannot parse enrollment date: '{raw.enrollment_date_raw}'",
            )

        flight_dt = self.parse_date(raw.flight_date_raw)
        dob_dt = self.parse_date(raw.dob_raw, is_dob=True)
        age = self.compute_age(dob_dt)
        is_stale, days_elapsed = self.compute_stale_status(flight_dt)
        canonical_country = self.standardize_country(raw.country_code_raw)

        staging_rec = StagingMemberRecord(
            member_id=str(raw.member_id).strip(),
            member_name=str(raw.member_name).strip(),
            enrollment_date=enroll_dt,
            flight_date=flight_dt,
            tier_code=raw.tier_code_raw.strip().upper() if raw.tier_code_raw else None,
            agent_name=raw.agent_name_raw.strip() if raw.agent_name_raw else None,
            state_code=raw.state_code_raw.strip().upper() if raw.state_code_raw else None,
            country_code=raw.country_code_raw.strip().upper() if raw.country_code_raw else "UNKNOWN",
            standardized_country=canonical_country,
            dob=dob_dt,
            is_active=raw.is_active_raw.strip().upper() if raw.is_active_raw else "A",
            age=age,
            stale_member=is_stale,
            days_since_last_flight=days_elapsed,
            source_line_num=raw.source_line_num,
        )
        return staging_rec, None
