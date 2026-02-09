"""CSV report writer for bounce analysis results."""

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FIELDNAMES = [
    "date",
    "folder",
    "error_code",
    "error_cause",
    "ai_responsible_party",
    "ai_reason",
    "from_addr",
    "to_addr",
    "subject",
    "body_plain",
    "body_html",
]


def write_reports(log_dir, account_name, target_records, excluded_records):
    """Write target and excluded bounce records to date-stamped CSV files.

    Files are only created when the record list is non-empty.
    """
    if not target_records and not excluded_records:
        logger.debug("No records for account '%s'; skipping CSV output.", account_name)
        return

    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")

    if target_records:
        target_path = out_dir / f"{date_str}_{account_name}_target.csv"
        _write_csv(target_path, target_records)
        logger.debug("Report: %s (%d rows)", target_path, len(target_records))

    if excluded_records:
        excluded_path = out_dir / f"{date_str}_{account_name}_excluded.csv"
        _write_csv(excluded_path, excluded_records)
        logger.debug("Report: %s (%d rows)", excluded_path, len(excluded_records))


def _write_csv(path, records):
    """Write a list of record dicts to a CSV file (UTF-8 with BOM)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
