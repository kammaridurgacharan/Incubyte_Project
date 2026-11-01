"""Unit tests for Country Router and 'Latest Record Wins' Relocation (TDD)."""

from datetime import date
import pytest
from src.skypoints.models import StagingMemberRecord
from src.skypoints.transforms.country_router import CountryRouter


def make_member(
    member_id: str,
    name: str,
    country: str,
    standardized: str,
    flight_date: date,
    tier: str = "GLD",
) -> StagingMemberRecord:
    return StagingMemberRecord(
        member_id=member_id,
        member_name=name,
        enrollment_date=date(2010, 10, 12),
        flight_date=flight_date,
        tier_code=tier,
        agent_name="Sam",
        state_code="CA",
        country_code=country,
        standardized_country=standardized,
        dob=date(1985, 3, 5),
        is_active="A",
        age=38,
        stale_member=False,
    )


def test_routes_members_to_respective_country_tables():
    router = CountryRouter()
    members = [
        make_member("1", "Elena", "USA", "USA", date(2024, 1, 10)),
        make_member("2", "Ravi", "IND", "India", date(2024, 1, 10)),
        make_member("3", "Nora", "CAN", "Canada", date(2024, 1, 10)),
        make_member("4", "Jacob", "AU", "Australia", date(2024, 1, 10)),
        make_member("5", "Mateo", "PHIL", "Philippines", date(2024, 1, 10)),
    ]
    router.process_batch(members)

    assert len(router.get_table("Table_USA")) == 1
    assert len(router.get_table("Table_India")) == 1
    assert len(router.get_table("Table_Canada")) == 1
    assert len(router.get_table("Table_Australia")) == 1
    assert len(router.get_table("Table_Philippines")) == 1


def test_within_batch_deduplication_latest_record_wins():
    router = CountryRouter()
    # Member Elena appears twice in same batch with different flight dates
    batch = [
        make_member("223457", "Elena", "USA", "USA", date(2024, 1, 5), tier="SLV"),
        make_member("223457", "Elena", "USA", "USA", date(2024, 1, 15), tier="GLD"),
    ]
    router.process_batch(batch)

    usa_table = router.get_table("Table_USA")
    assert len(usa_table) == 1
    # Latest record (2024-01-15, GLD) must win
    assert usa_table[0].tier_code == "GLD"
    assert usa_table[0].flight_date == date(2024, 1, 15)


def test_cross_country_relocation_cleans_up_previous_country():
    router = CountryRouter()

    # Day 1: Elena lives in USA
    day_1 = [make_member("223457", "Elena", "USA", "USA", date(2024, 1, 5))]
    router.process_batch(day_1)

    assert len(router.get_table("Table_USA")) == 1
    assert len(router.get_table("Table_India")) == 0

    # Day 2: Elena moves to India with a more recent flight date
    day_2 = [make_member("223457", "Elena", "IND", "India", date(2024, 1, 15))]
    router.process_batch(day_2)

    # Latest record wins: Elena should now be in Table_India and REMOVED from Table_USA
    assert len(router.get_table("Table_India")) == 1
    assert router.get_table("Table_India")[0].member_id == "223457"
    assert len(router.get_table("Table_USA")) == 0


def test_older_record_does_not_overwrite_newer_country():
    router = CountryRouter()

    # Day 1: Ravi in Canada on 2024-01-20
    router.process_batch([make_member("223458", "Ravi", "CAN", "Canada", date(2024, 1, 20))])
    assert len(router.get_table("Table_Canada")) == 1

    # Day 2: An out-of-order/stale feed arrives for Ravi in India on 2024-01-10
    router.process_batch([make_member("223458", "Ravi", "IND", "India", date(2024, 1, 10))])

    # Canadian record was newer (Jan 20 > Jan 10), so Canadian record must remain
    assert len(router.get_table("Table_Canada")) == 1
    assert len(router.get_table("Table_India")) == 0
