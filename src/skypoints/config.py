"""Configuration constants, business rules, and schema definitions for SkyPoints."""

from datetime import date
from typing import Dict, List, Set

# Expected Header layout in flat file (ignoring record type tag 'H' or 'D')
EXPECTED_HEADER_COLUMNS: List[str] = [
    "Member_Name",
    "Member_Id",
    "Enrollment_Date",
    "Last_Flight_Date",
    "Tier_Code",
    "Agent_Name",
    "State",
    "Country",
    "DOB",
    "Is_Active",
]

# Legacy Specification Column Definition (for schema drift detection)
LEGACY_SPEC_COLUMNS: List[str] = [
    "Member_Name",
    "Member_Id",
    "Enrollment_Date",
    "Last_Flight_Date",
    "Tier_Code",
    "Agent_Name",
    "State",
    "Country",
    "Post_Code",
    "Date_of_Birth",
    "Active_Member",
]

# Stale member criteria (days since last flight)
STALE_MEMBER_THRESHOLD_DAYS: int = 90

# Benchmark reference date for reproducible tests & batch processing (can be overridden)
DEFAULT_AS_OF_DATE: date = date(2024, 1, 15)

# Recognized ISO & Common Country Codes mapped to standardized table names
COUNTRY_TABLE_MAPPING: Dict[str, str] = {
    "USA": "Table_USA",
    "US": "Table_USA",
    "IND": "Table_India",
    "IN": "Table_India",
    "CAN": "Table_Canada",
    "CA": "Table_Canada",
    "AU": "Table_Australia",
    "AUS": "Table_Australia",
    "PHIL": "Table_Philippines",
    "PHL": "Table_Philippines",
    "PH": "Table_Philippines",
    "GBR": "Table_UK",
    "UK": "Table_UK",
    "DEU": "Table_Germany",
    "GER": "Table_Germany",
    "SGP": "Table_Singapore",
    "SG": "Table_Singapore",
    "UAE": "Table_UAE",
}

# Recognized Tier Codes
VALID_TIER_CODES: Set[str] = {"GLD", "SLV", "PLT", "BRZ", "BLU"}

# Recognized Active Status Flags
VALID_ACTIVE_FLAGS: Set[str] = {"A", "I"}

# Valid Redemption Statuses in JSON Feed
VALID_REDEMPTION_STATUSES: Set[str] = {"COMPLETED", "PENDING", "CANCELLED", "FAILED"}

