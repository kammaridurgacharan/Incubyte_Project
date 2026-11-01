"""Unit tests for Data Quality Validators (TDD)."""

from datetime import date
import pytest
from src.skypoints.models import StagingMemberRecord
from src.skypoints.quality.validators import DataQualityValidator


def make_valid_staging_record(
    member_id: str = "223457",
    name: str = "Elena",
    enrollment: date = date(2010, 10, 12),
    flight: date = date(2012, 10, 13),
    dob: date = date(1985, 3, 5),
    tier: str = "GLD",
    country: str = "USA",
    is_active: str = "A",
) -> StagingMemberRecord:
    return StagingMemberRecord(
        member_id=member_id,
        member_name=name,
        enrollment_date=enrollment,
        flight_date=flight,
        tier_code=tier,
        agent_name="Sam",
        state_code="CA",
        country_code=country,
        standardized_country=country,
        dob=dob,
        is_active=is_active,
        age=38,
        stale_member=True,
    )


def test_valid_record_passes_all_checks():
    validator = DataQualityValidator()
    rec = make_valid_staging_record()
    valid, errors = validator.validate_record(rec)

    assert valid is True
    assert len(errors) == 0


def test_mandatory_field_missing_fails():
    validator = DataQualityValidator()
    # Missing member name
    rec = make_valid_staging_record(name="")
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_MANDATORY_NULL" for e in errors)


def test_chronology_enrollment_after_flight_fails():
    validator = DataQualityValidator()
    # Flight in 2010, but enrollment in 2012 (impossible flight before loyalty enrollment)
    rec = make_valid_staging_record(
        enrollment=date(2012, 10, 12),
        flight=date(2010, 10, 13),
    )
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_CHRONOLOGY_VIOLATION" for e in errors)


def test_chronology_dob_after_enrollment_fails():
    validator = DataQualityValidator()
    # Enrolled in 2010, but born in 2015
    rec = make_valid_staging_record(
        enrollment=date(2010, 10, 12),
        dob=date(2015, 1, 1),
    )
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_INVALID_DOB_CHRONOLOGY" for e in errors)


def test_invalid_tier_code_fails():
    validator = DataQualityValidator()
    rec = make_valid_staging_record(tier="INVALID_TIER")
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_INVALID_TIER" for e in errors)


def test_invalid_active_flag_fails():
    validator = DataQualityValidator()
    rec = make_valid_staging_record(is_active="X")
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_INVALID_STATUS" for e in errors)


def test_batch_key_uniqueness_detects_conflicts():
    validator = DataQualityValidator()
    # Same member ID '223457' with conflicting names
    r1 = make_valid_staging_record(member_id="223457", name="Elena")
    r2 = make_valid_staging_record(member_id="223457", name="Imposter John")

    passed, quarantined = validator.validate_batch([r1, r2])
    
    # Both or conflicting duplicate flagged
    assert len(quarantined) > 0
    assert any(q.error_code == "ERR_DUPLICATE_KEY_CONFLICT" for q in quarantined)
