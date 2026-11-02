"""Unit tests for staging transformations (Age, Stale_Member, country normalization) (TDD)."""

from datetime import date
import pytest
from src.skypoints.models import RawMemberRecord
from src.skypoints.transforms.staging import StagingTransformer


def test_calculate_age_before_and_after_birthday():
    transformer = StagingTransformer(as_of_date=date(2024, 1, 15))
    
    # Born March 5, 1985 -> on Jan 15, 2024 birthday hasn't occurred yet -> Age is 38
    age_before = transformer.compute_age(date(1985, 3, 5))
    assert age_before == 38

    # Switch as_of_date to April 1, 2024 -> birthday has passed -> Age is 39
    transformer_after = StagingTransformer(as_of_date=date(2024, 4, 1))
    age_after = transformer_after.compute_age(date(1985, 3, 5))
    assert age_after == 39


def test_parse_dob_with_leading_zero_preservation():
    transformer = StagingTransformer()
    
    # 8-digit DOB '03051985'
    d1 = transformer.parse_date("03051985", is_dob=True)
    assert d1 == date(1985, 3, 5)

    # 7-digit DOB '3051985' (corrupted/dropped zero) -> should be auto-padded to '03051985'
    d2 = transformer.parse_date("3051985", is_dob=True)
    assert d2 == date(1985, 3, 5)


def test_stale_member_flag_threshold_90_days():
    # As of date 2024-01-15
    transformer = StagingTransformer(as_of_date=date(2024, 1, 15))

    # Flight on 2012-10-13 (thousands of days ago) -> Stale: True
    is_stale, days = transformer.compute_stale_status(date(2012, 10, 13))
    assert is_stale is True
    assert days > 90

    # Recent flight on 2024-01-05 (10 days ago) -> Stale: False
    is_stale_recent, days_recent = transformer.compute_stale_status(date(2024, 1, 5))
    assert is_stale_recent is False
    assert days_recent == 10

    # Exactly 90 days ago: 2023-10-17 -> Not stale (condition is > 90)
    is_stale_90, days_90 = transformer.compute_stale_status(date(2023, 10, 17))
    assert is_stale_90 is False
    assert days_90 == 90

    # 91 days ago: 2023-10-16 -> Stale: True
    is_stale_91, days_91 = transformer.compute_stale_status(date(2023, 10, 16))
    assert is_stale_91 is True
    assert days_91 == 91

    # Never flown (flight_date is None) -> Stale: True
    is_stale_none, days_none = transformer.compute_stale_status(None)
    assert is_stale_none is True
    assert days_none is None


def test_country_normalization_for_sample_data():
    transformer = StagingTransformer()
    
    assert transformer.standardize_country("USA") == "USA"
    assert transformer.standardize_country("IND") == "India"
    assert transformer.standardize_country("PHIL") == "Philippines"
    assert transformer.standardize_country("CAN") == "Canada"
    assert transformer.standardize_country("AU") == "Australia"
    assert transformer.standardize_country("phl") == "Philippines"


def test_transform_raw_to_staging_record():
    transformer = StagingTransformer(as_of_date=date(2024, 1, 15))
    raw = RawMemberRecord(
        record_type="D",
        member_name="Elena",
        member_id="223457",
        enrollment_date_raw="20101012",
        flight_date_raw="20121013",
        tier_code_raw="GLD",
        agent_name_raw="Sam",
        state_code_raw="CA",
        country_code_raw="USA",
        dob_raw="03051985",
        is_active_raw="A",
    )
    staging_rec, error = transformer.transform(raw)

    assert error is None
    assert staging_rec is not None
    assert staging_rec.member_name == "Elena"
    assert staging_rec.member_id == "223457"
    assert staging_rec.enrollment_date == date(2010, 10, 12)
    assert staging_rec.flight_date == date(2012, 10, 13)
    assert staging_rec.dob == date(1985, 3, 5)
    assert staging_rec.age == 38
    assert staging_rec.stale_member is True
    assert staging_rec.standardized_country == "USA"

