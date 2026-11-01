# SkyPoints Data Dictionary & Schema Specification

## 1. Member Profile Feed Specification

### A. Record Types
* `|H|`: Header row containing column names.
* `|D|`: Detail row containing member profile data.

### B. Field Specifications & Business Rules

| Pos | Field Name | Target Column | Target Type | Mandatory | Key? | Description & Parsing Rules |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| - | Record_Type | `record_type` | `CHAR(1)` | Y | N | Identifies row type: 'H' for header, 'D' for detail. |
| 1 | Member Name | `member_name` | `VARCHAR(255)` | Y | N* | Full name of the loyalty member. (*Marked Key in legacy spec, but treated as non-unique biographical field). |
| 2 | Member ID | `member_id` | `VARCHAR(18)` | Y | **Y** | Unique membership identifier (alphanumeric, 4 to 18 chars). True business key. |
| 3 | Enrollment Date | `enrollment_date` | `DATE` | Y | N | Date of loyalty program enrollment (format: `YYYYMMDD`). |
| 4 | Last Flight Date | `last_flight_date`| `DATE` | N | N | Most recent flight completed (format: `YYYYMMDD`). Can be NULL for new non-flying members. |
| 5 | Tier Code | `tier_code` | `VARCHAR(5)` | N | N | Membership tier: `GLD` (Gold), `SLV` (Silver), `PLT` (Platinum), etc. |
| 6 | Agent Name | `agent_name` | `VARCHAR(255)` | N | N | Customer support agent or enrollment channel representative. Optional. |
| 7 | State | `state_code` | `VARCHAR(5)` | N | N | State or province abbreviation (e.g., `CA`, `TN`, `NCR`, `VIC`, `ONT`). |
| 8 | Country | `country_code` | `VARCHAR(10)` | Y | N | Country code (e.g., `USA`, `IND`, `PHIL`, `CAN`, `AU`). Standardized to canonical table routing. |
| 9 | Date of Birth | `dob` | `DATE` | N | N | Member date of birth (format: `MMDDYYYY` or `DDMMYYYY`). Handled with leading-zero preservation. |
| 10 | Active Member | `is_active` | `CHAR(1)` | N | N | Status indicator: `'A'` (Active), `'I'` (Inactive). Defaults to `'A'`. |

---

## 2. Staging Layer Derived Columns

| Column Name | Type | Expression / Logic | Purpose |
| :--- | :--- | :--- | :--- |
| `age` | `INTEGER` | Completed years between `dob` and reference date (`as_of_date`). | Personalization, demographics, age-restricted promotions. |
| `stale_member` | `BOOLEAN` | `DATEDIFF(day, last_flight_date, as_of_date) > 90` | Identifies churn-risk members with no activity in past quarter. |
| `days_since_last_flight` | `INTEGER` | `DATEDIFF(day, last_flight_date, as_of_date)` | Granular recency metric for loyalty retention campaigns. |
| `canonical_country` | `VARCHAR(50)` | Lookup standard name (`USA`, `India`, `Canada`, `Australia`, `Philippines`). | Determines routing to target country table. |
| `load_timestamp` | `TIMESTAMP` | Current UTC timestamp when batch was processed. | Lineage and auditability. |

---

## 3. Semi-Structured JSON Redemption Feed Specification

### A. Root Feed Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `member_id` | `VARCHAR(18)` | Member ID foreign key matching Member Profile. |
| `feed_date` | `VARCHAR(8)` | Date partner feed was generated (`YYYYMMDD`). |
| `redemptions` | `ARRAY[OBJECT]` | Nested array of transaction objects. |

### B. Nested Redemption Transaction Object (`redemptions[*]`)

| Field | Target Type | Mandatory | Description |
| :--- | :--- | :--- | :--- |
| `txn_id` | `VARCHAR(50)` | Y | Unique transaction ID (e.g., `RX10091`). Primary key. |
| `txn_date` | `DATE` | Y | Date of redemption (`YYYYMMDD`). |
| `partner` | `VARCHAR(100)` | Y | Partner airline or service (e.g., `AeroLink`, `SkyPoints`). |
| `miles_redeemed`| `INTEGER` | Y | Quantity of miles redeemed (positive integer). |
| `status` | `VARCHAR(20)` | Y | Transaction status: `COMPLETED`, `PENDING`, `CANCELLED`. |

---

## 4. Anomalies & Quality Rules Discovered in Sample Data

1. **Schema Drift**: Position 9 in legacy spec was `Post Code`, but real feed row has `DOB`. Ingestion layer binds by column name from Header row (`|H|...`).
2. **Missing Agent Name / Shifting**: When optional fields are omitted or delimiter spacing varies, empty strings are cast to `NULL` to avoid column shifting.
3. **Leading Zero DOB Loss**: Raw values like `3051985` are left-padded to 8 characters (`03051985`) prior to date parsing.
4. **Country Normalization**:
   * `PHIL` $\to$ `Philippines` (`Table_Philippines`)
   * `AU` $\to$ `Australia` (`Table_Australia`)
   * `IND` $\to$ `India` (`Table_India`)
   * `USA` $\to$ `USA` (`Table_USA`)
   * `CAN` $\to$ `Canada` (`Table_Canada`)
