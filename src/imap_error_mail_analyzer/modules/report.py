"""JSON report writer for bounce analysis results."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FIELD_KEYS = [
    "date",
    "folder",
    "error_code",
    "error_message",
    "ai_responsible_party",
    "ai_reason",
    "from_addr",
    "to_addr",
    "subject",
    "body_plain",
    "body_html",
    "body_plain_original",
    "body_html_original",
    "delivery_status",
]


def write_reports(log_dir, account_name, target_records, excluded_records):
    """Write target and excluded bounce records to date-stamped JSON files.

    Files are only created when the record list is non-empty.
    """
    if not target_records and not excluded_records:
        logger.debug("No records for account '%s'; skipping report output.", account_name)
        return

    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")

    if target_records:
        target_path = out_dir / f"{date_str}_{account_name}_target.json"
        _write_json(target_path, target_records)
        logger.debug("Report: %s (%d records)", target_path, len(target_records))

    if excluded_records:
        excluded_path = out_dir / f"{date_str}_{account_name}_excluded.json"
        _write_json(excluded_path, excluded_records)
        logger.debug("Report: %s (%d records)", excluded_path, len(excluded_records))


def _write_json(path, records):
    """Write a list of record dicts to a formatted JSON file (UTF-8).

    If the file already exists, new records are appended to avoid
    overwriting results from a previous run on the same day.
    """
    existing = []
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []
    merged = existing + records
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
