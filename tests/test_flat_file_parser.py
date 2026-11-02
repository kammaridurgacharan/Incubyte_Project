"""Unit tests for flat file ingestion parser (TDD)."""

import pytest
from src.skypoints.ingestion.flat_file_parser import FlatFileParser
from src.skypoints.models import RawMemberRecord


SAMPLE_FEED = (
    "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active\n"
    "|D|Elena|223457|20101012|20121013|GLD|Sam|CA|USA|03051985|A\n"
    "|D|Ravi|223458|20101012|20121013|SLV|Sam|TN|IND|03051985|A\n"
    "|D|Mateo|223459|20101012|20121013|GLD|Sam|NCR|PHIL|03051985|A\n"
    "|D|Nora|22345|20101012|20121013|PLT|Sam|ONT|CAN|03051985|A\n"
    "|D|Jacob|2256|20101012|20121013|SLV|Sam|VIC|AU|03051985|A\n"
)


def test_parser_extracts_header():
    parser = FlatFileParser()
    headers, records, errors = parser.parse_text(SAMPLE_FEED)
    
    assert len(headers) == 10
    assert headers[0] == "Member_Name"
    assert headers[1] == "Member_Id"
    assert headers[-1] == "Is_Active"
    assert len(records) == 5
    assert len(errors) == 0


def test_parser_detects_schema_drift():
    parser = FlatFileParser()
    parser.parse_text(SAMPLE_FEED)
    
    # In SAMPLE_FEED, 'Post_Code' from legacy spec is absent
    assert any("Post_Code" in drift for drift in parser.detected_drifts)


def test_parser_preserves_leading_zeros_in_dob():
    parser = FlatFileParser()
    _, records, _ = parser.parse_text(SAMPLE_FEED)
    
    elena = records[0]
    assert elena.member_name == "Elena"
    assert elena.member_id == "223457"
    assert elena.dob_raw == "03051985"


def test_parser_handles_different_country_lengths():
    parser = FlatFileParser()
    _, records, _ = parser.parse_text(SAMPLE_FEED)
    
    countries = [r.country_code_raw for r in records]
    assert countries == ["USA", "IND", "PHIL", "CAN", "AU"]


def test_parser_handles_empty_optional_fields():
    line_with_empty_agent = (
        "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active\n"
        "|D|Ravi|223458|20101012|20121013|SLV||TN|IND|03051985|A\n"
    )
    parser = FlatFileParser()
    _, records, errors = parser.parse_text(line_with_empty_agent)
    
    assert len(records) == 1
    assert records[0].member_name == "Ravi"
    assert records[0].agent_name_raw is None or records[0].agent_name_raw == ""
    assert records[0].state_code_raw == "TN"
    assert records[0].country_code_raw == "IND"


def test_parser_quarantines_malformed_lines():
    bad_feed = (
        "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active\n"
        "|D|IncompleteRow|12345|20200101\n"
    )
    parser = FlatFileParser()
    _, records, errors = parser.parse_text(bad_feed)
    
    assert len(records) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "ERR_MALFORMED_DELIMITER_ROW"


def test_parser_handles_empty_content():
    parser = FlatFileParser()
    headers, records, errors = parser.parse_text("   \n\n  ")
    assert len(headers) == 0
    assert len(records) == 0
    assert len(errors) == 0


def test_parser_handles_header_only_feed():
    header_only = "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active\n"
    parser = FlatFileParser()
    headers, records, errors = parser.parse_text(header_only)
    assert len(headers) == 10
    assert len(records) == 0
    assert len(errors) == 0
