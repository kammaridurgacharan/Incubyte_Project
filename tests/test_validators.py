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
    age: int = 38,
    source_line_num: int = 42,
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
        age=age,
        stale_member=True,
        source_line_num=source_line_num,
    )


def test_valid_record_passes_all_checks():
    validator = DataQualityValidator()
    rec = make_valid_staging_record()
    valid, errors = validator.validate_record(rec)

    assert valid is True
    assert len(errors) == 0


def test_mandatory_field_missing_fails():
    validator = DataQualityValidator()
    rec = make_valid_staging_record(name="")
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_MANDATORY_NULL" for e in errors)
    # Verify line number propagation
    assert errors[0].source_line_num == 42


def test_chronology_enrollment_after_flight_fails():
    validator = DataQualityValidator()
    rec = make_valid_staging_record(
        enrollment=date(2012, 10, 12),
        flight=date(2010, 10, 13),
    )
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_CHRONOLOGY_VIOLATION" for e in errors)


def test_chronology_dob_after_enrollment_fails():
    validator = DataQualityValidator()
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


def test_extreme_age_fails_biological_sanity():
    validator = DataQualityValidator()
    rec = make_valid_staging_record(age=150)
    valid, errors = validator.validate_record(rec)

    assert valid is False
    assert any(e.error_code == "ERR_BIOLOGICAL_SANITY" for e in errors)


def test_batch_key_uniqueness_detects_conflicts():
    validator = DataQualityValidator()
    r1 = make_valid_staging_record(member_id="223457", name="Elena", source_line_num=10)
    r2 = make_valid_staging_record(member_id="223457", name="Imposter John", source_line_num=11)

    passed, quarantined = validator.validate_batch([r1, r2])
    
    assert len(quarantined) > 0
    assert any(q.error_code == "ERR_DUPLICATE_KEY_CONFLICT" for q in quarantined)
    assert any(q.source_line_num == 10 or q.source_line_num == 11 for q in quarantined)
