"""Data models and schemas for SkyPoints loyalty pipeline."""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Returns current UTC timestamp in a timezone-aware format."""
    return datetime.now(timezone.utc)


class RawMemberRecord(BaseModel):
    """Raw record directly parsed from flat file before type casting."""
    record_type: str = Field(description="Record marker, expected 'D'")
    member_name: Optional[str] = None
    member_id: Optional[str] = None
    enrollment_date_raw: Optional[str] = None
    flight_date_raw: Optional[str] = None
    tier_code_raw: Optional[str] = None
    agent_name_raw: Optional[str] = None
    state_code_raw: Optional[str] = None
    country_code_raw: Optional[str] = None
    dob_raw: Optional[str] = None
    is_active_raw: Optional[str] = None
    source_line_num: int = 0


class StagingMemberRecord(BaseModel):
    """Cleaned, typed, and enriched member record in staging layer."""
    member_id: str
    member_name: str
    enrollment_date: date
    flight_date: Optional[date] = None
    tier_code: Optional[str] = None
    agent_name: Optional[str] = None
    state_code: Optional[str] = None
    country_code: str
    standardized_country: str
    dob: Optional[date] = None
    is_active: str = "A"
    age: Optional[int] = None
    stale_member: bool = False
    days_since_last_flight: Optional[int] = None
    source_line_num: int = 0
    batch_id: Optional[str] = None
    processed_at: datetime = Field(default_factory=utc_now)


class FlattenedRedemptionRecord(BaseModel):
    """Flattened transaction item from semi-structured JSON redemption feed."""
    txn_id: str
    member_id: str
    feed_date: date
    txn_date: date
    partner: str
    miles_redeemed: int
    status: str
    source_line_num: int = 0
    processed_at: datetime = Field(default_factory=utc_now)


class QuarantineRecord(BaseModel):
    """Record that failed schema, mandatory, or integrity validations."""
    source_line_num: int = 0
    raw_payload: str
    error_code: str
    error_message: str
    quarantined_at: datetime = Field(default_factory=utc_now)
