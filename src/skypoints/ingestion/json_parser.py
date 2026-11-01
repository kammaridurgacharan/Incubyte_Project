"""Semi-structured JSON redemption feed parser and flattener."""

from datetime import datetime, date
import json
from typing import Any, Dict, List, Tuple
from src.skypoints.models import FlattenedRedemptionRecord, QuarantineRecord


class JsonRedemptionParser:
    """Parses and flattens semi-structured JSON redemption transaction feeds."""

    def __init__(self, date_format: str = "%Y%m%d") -> None:
        self.date_format = date_format

    def parse_file(self, file_path: str) -> Tuple[List[FlattenedRedemptionRecord], List[QuarantineRecord]]:
        """Parses a JSON feed file from disk."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_text(content)

    def parse_text(self, content: str) -> Tuple[List[FlattenedRedemptionRecord], List[QuarantineRecord]]:
        """Parses JSON text into flattened redemption records."""
        try:
            raw_data = json.loads(content)
        except Exception as e:
            return [], [
                QuarantineRecord(
                    source_line_num=1,
                    raw_payload=content[:500],
                    error_code="ERR_INVALID_JSON_PAYLOAD",
                    error_message=f"JSON decoding failed: {str(e)}",
                )
            ]

        # Normalize to list of member payloads
        member_payloads: List[Dict[str, Any]] = raw_data if isinstance(raw_data, list) else [raw_data]

        records: List[FlattenedRedemptionRecord] = []
        errors: List[QuarantineRecord] = []

        for idx, payload in enumerate(member_payloads, start=1):
            member_id = payload.get("member_id")
            feed_date_str = payload.get("feed_date")

            if not member_id or not feed_date_str:
                errors.append(
                    QuarantineRecord(
                        source_line_num=idx,
                        raw_payload=json.dumps(payload),
                        error_code="ERR_MISSING_HEADER_KEYS",
                        error_message="Missing mandatory member_id or feed_date in JSON root",
                    )
                )
                continue

            try:
                feed_date = datetime.strptime(str(feed_date_str), self.date_format).date()
            except ValueError:
                errors.append(
                    QuarantineRecord(
                        source_line_num=idx,
                        raw_payload=json.dumps(payload),
                        error_code="ERR_INVALID_DATE_FORMAT",
                        error_message=f"Invalid feed_date '{feed_date_str}', expected {self.date_format}",
                    )
                )
                continue

            redemptions_list = payload.get("redemptions", [])
            if not isinstance(redemptions_list, list):
                errors.append(
                    QuarantineRecord(
                        source_line_num=idx,
                        raw_payload=json.dumps(payload),
                        error_code="ERR_MALFORMED_REDEMPTIONS_ARRAY",
                        error_message="Field 'redemptions' must be an array of objects",
                    )
                )
                continue

            for txn in redemptions_list:
                if not isinstance(txn, dict):
                    continue

                txn_id = txn.get("txn_id")
                txn_date_str = txn.get("txn_date")
                partner = txn.get("partner")
                miles = txn.get("miles_redeemed")
                status = txn.get("status", "COMPLETED")

                if not txn_id or not txn_date_str or not partner or miles is None:
                    errors.append(
                        QuarantineRecord(
                            source_line_num=idx,
                            raw_payload=json.dumps(txn),
                            error_code="ERR_INVALID_REDEMPTION_ITEM",
                            error_message="Redemption item missing txn_id, txn_date, partner, or miles_redeemed",
                        )
                    )
                    continue

                try:
                    txn_date = datetime.strptime(str(txn_date_str), self.date_format).date()
                    miles_int = int(miles)
                except (ValueError, TypeError) as conv_err:
                    errors.append(
                        QuarantineRecord(
                            source_line_num=idx,
                            raw_payload=json.dumps(txn),
                            error_code="ERR_TYPE_CONVERSION",
                            error_message=f"Conversion error in redemption item: {str(conv_err)}",
                        )
                    )
                    continue

                records.append(
                    FlattenedRedemptionRecord(
                        txn_id=str(txn_id),
                        member_id=str(member_id),
                        feed_date=feed_date,
                        txn_date=txn_date,
                        partner=str(partner),
                        miles_redeemed=miles_int,
                        status=str(status).upper(),
                    )
                )

        return records, errors
