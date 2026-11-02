"""End-to-End Pipeline Integration Tests (TDD)."""

from datetime import date
from pathlib import Path
import pytest
from src.skypoints.pipeline import SkyPointsPipeline


DATA_DIR = Path(__file__).parent.parent / "data"


def test_pipeline_e2e_with_sample_data():
    flat_file = str(DATA_DIR / "sample_members.dat")
    json_file = str(DATA_DIR / "sample_redemptions.json")

    pipeline = SkyPointsPipeline(as_of_date=date(2024, 1, 15))
    result = pipeline.run(flat_file_path=flat_file, json_file_path=json_file)

    # 1. Verification of Ingestion & Staging
    assert result.raw_records_count == 5
    assert result.staged_records_count == 5
    assert result.quarantined_count == 0

    # 2. Verification of Derived Columns in Staging
    elena = next(r for r in result.staged_records if r.member_id == "223457")
    assert elena.age == 38
    assert elena.stale_member is True
    assert elena.standardized_country == "USA"

    # 3. Verification of Country-Specific Target Tables
    assert len(result.country_tables["Table_USA"]) == 1
    assert result.country_tables["Table_USA"][0].member_name == "Elena"

    assert len(result.country_tables["Table_India"]) == 1
    assert result.country_tables["Table_India"][0].member_name == "Ravi"

    assert len(result.country_tables["Table_Philippines"]) == 1
    assert result.country_tables["Table_Philippines"][0].member_name == "Mateo"

    assert len(result.country_tables["Table_Canada"]) == 1
    assert result.country_tables["Table_Canada"][0].member_name == "Nora"

    assert len(result.country_tables["Table_Australia"]) == 1
    assert result.country_tables["Table_Australia"][0].member_name == "Jacob"

    # 4. Verification of Semi-Structured JSON Flattening
    assert result.redemptions_count == 4

    # 5. Verification of Analytical SQL Join (Member Profile <-> Redemptions)
    summary_list = result.analytical_summary
    assert len(summary_list) == 5

    elena_summary = next(s for s in summary_list if s["member_id"] == "223457")
    assert elena_summary["total_transactions"] == 2
    assert elena_summary["total_miles_redeemed"] == 17000
    assert elena_summary["completed_miles"] == 12000
    assert elena_summary["pending_miles"] == 5000

    ravi_summary = next(s for s in summary_list if s["member_id"] == "223458")
    assert ravi_summary["total_transactions"] == 1
    assert ravi_summary["total_miles_redeemed"] == 8500


def test_pipeline_member_relocation_across_batches():
    relocation_file = str(DATA_DIR / "multi_day_relocation.dat")

    pipeline = SkyPointsPipeline(as_of_date=date(2024, 1, 15))
    result = pipeline.run(flat_file_path=relocation_file)

    # In multi_day_relocation.dat:
    # Elena moves from USA (Jan 10) to IND (Jan 15)
    # Ravi moves from IND (Dec 1) to CAN (Jan 14)
    # Elena must now be in Table_India and NOT in Table_USA
    # Ravi must now be in Table_Canada and NOT in Table_India
    india_members = [r.member_name for r in result.country_tables["Table_India"]]
    usa_members = [r.member_name for r in result.country_tables.get("Table_USA", [])]
    canada_members = [r.member_name for r in result.country_tables["Table_Canada"]]

    assert "Elena" in india_members
    assert "Elena" not in usa_members
    assert "Ravi" in canada_members
    assert "Ravi" not in india_members


def test_pipeline_exports_country_csvs(tmp_path):
    flat_file = str(DATA_DIR / "sample_members.dat")
    pipeline = SkyPointsPipeline(as_of_date=date(2024, 1, 15))
    pipeline.run(flat_file_path=flat_file)

    exported = pipeline.export_country_tables(output_dir=str(tmp_path / "exports"))
    assert "Table_India" in exported
    assert "Table_USA" in exported
    assert "Table_Australia" in exported

    ind_file = tmp_path / "exports" / "IND.csv"
    usa_file = tmp_path / "exports" / "USA.csv"
    aus_file = tmp_path / "exports" / "AUS.csv"

    assert ind_file.exists()
    assert usa_file.exists()
    assert aus_file.exists()
    assert "Ravi" in ind_file.read_text(encoding="utf-8")
    assert "Elena" in usa_file.read_text(encoding="utf-8")
    assert "Jacob" in aus_file.read_text(encoding="utf-8")

