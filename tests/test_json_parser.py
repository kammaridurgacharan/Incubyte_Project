"""Unit tests for semi-structured JSON redemption feed parser (TDD)."""

from datetime import date
import pytest
from src.skypoints.ingestion.json_parser import JsonRedemptionParser


SAMPLE_SINGLE_JSON = """
{
  "member_id": "223457",
  "feed_date": "20240115",
  "redemptions": [
    { "txn_id": "RX10091", "txn_date": "20240110", "partner": "AeroLink", "miles_redeemed": 12000, "status": "COMPLETED" },
    { "txn_id": "RX10092", "txn_date": "20240113", "partner": "SkyPoints", "miles_redeemed": 5000, "status": "PENDING" }
  ]
}
"""

SAMPLE_ARRAY_JSON = """
[
  {
    "member_id": "223457",
    "feed_date": "20240115",
    "redemptions": [
      { "txn_id": "RX10091", "txn_date": "20240110", "partner": "AeroLink", "miles_redeemed": 12000, "status": "COMPLETED" }
    ]
  },
  {
    "member_id": "223458",
    "feed_date": "20240115",
    "redemptions": [
      { "txn_id": "RX10093", "txn_date": "20240112", "partner": "IndiGoAir", "miles_redeemed": 8500, "status": "COMPLETED" }
    ]
  }
]
"""


def test_parse_single_json_member_payload():
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text(SAMPLE_SINGLE_JSON)

    assert len(errors) == 0
    assert len(records) == 2

    r1 = records[0]
    assert r1.txn_id == "RX10091"
    assert r1.member_id == "223457"
    assert r1.feed_date == date(2024, 1, 15)
    assert r1.txn_date == date(2024, 1, 10)
    assert r1.partner == "AeroLink"
    assert r1.miles_redeemed == 12000
    assert r1.status == "COMPLETED"

    r2 = records[1]
    assert r2.txn_id == "RX10092"
    assert r2.miles_redeemed == 5000
    assert r2.status == "PENDING"


def test_parse_array_json_payload():
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text(SAMPLE_ARRAY_JSON)

    assert len(errors) == 0
    assert len(records) == 2
    assert records[0].member_id == "223457"
    assert records[1].member_id == "223458"


def test_parse_quarantines_corrupted_redemption_items():
    corrupted_json = """
    {
      "member_id": "999999",
      "feed_date": "20240115",
      "redemptions": [
        { "txn_id": "RX_GOOD", "txn_date": "20240110", "partner": "Aero", "miles_redeemed": 1000, "status": "COMPLETED" },
        { "partner": "NoTxnId", "miles_redeemed": 500 }
      ]
    }
    """
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text(corrupted_json)

    assert len(records) == 1
    assert records[0].txn_id == "RX_GOOD"
    assert len(errors) == 1
    assert errors[0].error_code == "ERR_INVALID_REDEMPTION_ITEM"


def test_parse_quarantines_negative_miles():
    negative_miles_json = """
    {
      "member_id": "223457",
      "feed_date": "20240115",
      "redemptions": [
        { "txn_id": "RX_NEG", "txn_date": "20240110", "partner": "AeroLink", "miles_redeemed": -5000, "status": "COMPLETED" }
      ]
    }
    """
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text(negative_miles_json)

    assert len(records) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "ERR_NEGATIVE_MILES"


def test_parse_quarantines_invalid_status():
    invalid_status_json = """
    {
      "member_id": "223457",
      "feed_date": "20240115",
      "redemptions": [
        { "txn_id": "RX_STATUS", "txn_date": "20240110", "partner": "AeroLink", "miles_redeemed": 5000, "status": "UNKNOWN_STATUS" }
      ]
    }
    """
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text(invalid_status_json)

    assert len(records) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "ERR_INVALID_REDEMPTION_STATUS"


def test_parse_handles_malformed_syntax():
    parser = JsonRedemptionParser()
    records, errors = parser.parse_text("{bad_json: True,")

    assert len(records) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "ERR_INVALID_JSON_PAYLOAD"
