"""SkyPoints Global Loyalty Data Pipeline - Live Demonstration.

Executes end-to-end ingestion, staging derivations, quality quarantine,
country routing, JSON flattening, and member loyalty summary analytics.

Usage:
    python demo.py
"""

from datetime import date
from pathlib import Path

from src.skypoints.config import DEFAULT_AS_OF_DATE
from src.skypoints.pipeline import SkyPointsPipeline


def print_banner(title: str) -> None:
    print("\n" + "=" * 80)
    print(f"  {title.upper()}")
    print("=" * 80)


def print_sub_banner(title: str) -> None:
    print("\n" + "-" * 70)
    print(f"[*] {title}")
    print("-" * 70)


def main() -> None:
    print_banner("SkyPoints Global Airline Loyalty Data Engineering Platform")
    print(f"Pipeline Reference As-Of Date: {DEFAULT_AS_OF_DATE}")

    data_dir = Path(__file__).parent / "data"
    sample_flat_file = str(data_dir / "sample_members.dat")
    sample_json_file = str(data_dir / "sample_redemptions.json")

    pipeline = SkyPointsPipeline(as_of_date=DEFAULT_AS_OF_DATE)

    # -------------------------------------------------------------------------
    # STAGE 1: INGESTION & STAGING WITH DERIVED COLUMNS
    # -------------------------------------------------------------------------
    print_sub_banner("1. Loading Flat File Profiles & Computing Staging Derivations")
    print(f"Reading: {sample_flat_file}")
    print(f"Reading: {sample_json_file}")

    result = pipeline.run(
        flat_file_path=sample_flat_file,
        json_file_path=sample_json_file,
        batch_id="batch_day1_sample",
        reset_state=True,
    )

    print("\nIngestion Metrics:")
    print(f"  - Active Batch ID            : {result.batch_id}")
    print(f"  - Raw Records Ingested       : {result.raw_records_count}")
    print(f"  - Staged Valid Members       : {result.staged_records_count}")
    print(f"  - Quarantined Records        : {result.quarantined_count}")
    print(f"  - Flattened Redemptions      : {result.redemptions_count}")

    print("\n[STAGING TABLE PREVIEW: Derived Age and Stale_Member Flag (>90 days)]")
    staging_fmt = "{:<8} {:<10} {:<10} {:<10} {:<5} {:<6} {:<12} {:<4} {:<6} {:<12}"
    print(staging_fmt.format("Name", "Mem_Id", "Enroll_Dt", "Flight_Dt", "Tier", "State", "Country", "Age", "Stale?", "Days_Elapsed"))
    print("-" * 90)
    for s in result.staged_records:
        print(
            staging_fmt.format(
                s.member_name,
                s.member_id,
                s.enrollment_date.strftime("%Y%m%d"),
                s.flight_date.strftime("%Y%m%d") if s.flight_date else "N/A",
                s.tier_code or "",
                s.state_code or "",
                s.standardized_country,
                s.age if s.age is not None else "N/A",
                "TRUE" if s.stale_member else "FALSE",
                s.days_since_last_flight if s.days_since_last_flight is not None else "N/A",
            )
        )

    # -------------------------------------------------------------------------
    # STAGE 2: COUNTRY-SPECIFIC TARGET TABLES
    # -------------------------------------------------------------------------
    print_sub_banner("2. Country-Specific Target Tables (Table_<Country>)")
    for tbl_name, rows in sorted(result.country_tables.items()):
        print(f"\n--> {tbl_name} ({len(rows)} members):")
        for r in rows:
            print(f"      * Member ID: {r.member_id:<8} | Name: {r.member_name:<8} | Tier: {r.tier_code} | Age: {r.age} | State: {r.state_code}")

    # -------------------------------------------------------------------------
    # STAGE 2b: EXPORT REGIONAL COUNTRY FILES (IND.csv, USA.csv, AUS.csv)
    # -------------------------------------------------------------------------
    print_sub_banner("2b. Exporting Regional Files (IND.csv, USA.csv, AUS.csv)")
    exported_files = pipeline.export_country_tables(output_dir="output")
    for tbl, path in sorted(exported_files.items()):
        print(f"  - {tbl:<18} -> {path}")

    # -------------------------------------------------------------------------
    # STAGE 3: SEMI-STRUCTURED JSON FLATTENING
    # -------------------------------------------------------------------------
    print_sub_banner("3. Flattened Semi-Structured JSON Redemptions (FACT_REDEMPTIONS)")
    red_fmt = "{:<10} {:<10} {:<12} {:<12} {:<12} {:<10} {:<12}"
    print(red_fmt.format("Txn_ID", "Member_ID", "Feed_Date", "Txn_Date", "Partner", "Miles", "Status"))
    print("-" * 82)
    for red in result.redemption_records:
        print(
            red_fmt.format(
                red.txn_id,
                red.member_id,
                red.feed_date.strftime("%Y%m%d"),
                red.txn_date.strftime("%Y%m%d"),
                red.partner,
                red.miles_redeemed,
                red.status,
            )
        )

    # -------------------------------------------------------------------------
    # STAGE 4: ANALYTICAL SQL JOIN (Member Profile <-> Redemptions)
    # -------------------------------------------------------------------------
    print_sub_banner("4. Analytical SQL View: 360-Degree Member Loyalty Summary")
    join_fmt = "{:<8} {:<8} {:<5} {:<12} {:<4} {:<6} {:<10} {:<12} {:<10} {:<10}"
    print(join_fmt.format("Mem_ID", "Name", "Tier", "Country", "Age", "Stale?", "Txn_Count", "Total_Miles", "Completed", "Pending"))
    print("-" * 92)
    for row in result.analytical_summary:
        print(
            join_fmt.format(
                row["member_id"],
                row["member_name"],
                row["tier_code"] or "",
                row["standardized_country"],
                row["age"] if row["age"] is not None else "N/A",
                "YES" if row["stale_member"] else "NO",
                row["total_transactions"],
                row["total_miles_redeemed"],
                row["completed_miles"],
                row["pending_miles"],
            )
        )

    # -------------------------------------------------------------------------
    # STAGE 5: LATEST-RECORD-WINS & MEMBER RELOCATION DEMO
    # -------------------------------------------------------------------------
    print_sub_banner("5. Demonstration of 'Latest Record Wins' with Member Relocation")
    print("Scenario: Elena moves from USA to India (Flight 2024-01-15), Ravi moves from India to Canada (Flight 2024-01-14)")
    relocation_file = str(data_dir / "multi_day_relocation.dat")
    relo_result = pipeline.run(flat_file_path=relocation_file, batch_id="batch_day2_relocation", reset_state=False)

    print("\nState of Country Tables After Relocation Feed:")
    for tbl_name in ["Table_USA", "Table_India", "Table_Canada"]:
        members = [f"{r.member_name} ({r.member_id})" for r in relo_result.country_tables.get(tbl_name, [])]
        print(f"  - {tbl_name:<16}: {', '.join(members) if members else '[EMPTY - Member moved out!]'}")

    # -------------------------------------------------------------------------
    # STAGE 6: DATA QUALITY VALIDATION & DEAD-LETTER QUARANTINE
    # -------------------------------------------------------------------------
    print_sub_banner("6. Data Quality Engine: Isolation of Corrupt Records (Quarantine)")
    dirty_feed = (
        "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active\n"
        "|D||999001|20200101|20230101|GLD|Sam|CA|USA|01011990|A\n"             # Missing Member_Name (Line 2)
        "|D|FutureFlier|999002|20230101|20200101|GLD|Sam|CA|USA|01011990|A\n"     # Flight before Enrollment (Line 3)
        "|D|BabyTraveler|999003|20200101|20230101|GLD|Sam|CA|USA|01012025|A\n"   # Born in 2025 (after enrollment) (Line 4)
        "|D|BadTier|999004|20200101|20230101|DIAMOND|Sam|CA|USA|01011990|A\n"     # Unrecognized Tier (Line 5)
        "|D|ShortLine|999005\n"                                                    # Truncated delimiter line (Line 6)
    )

    dq_pipeline = SkyPointsPipeline(as_of_date=DEFAULT_AS_OF_DATE)
    dq_result = dq_pipeline.run(flat_file_text=dirty_feed, batch_id="batch_dirty_test", reset_state=True)
    print(f"Injected 5 intentional data corruptions. Quarantined: {dq_result.quarantined_count} records.\n")
    q_fmt = "{:<6} {:<28} {:<45}"
    print(q_fmt.format("Line", "Error Code", "Error Message"))
    print("-" * 80)
    for q in dq_result.quarantined_records:
        print(q_fmt.format(q.source_line_num, q.error_code, q.error_message[:44]))

    print_banner("SkyPoints Pipeline Execution Completed Successfully")


if __name__ == "__main__":
    main()
