"""CLI command implementations for IMAP Error Mail Analyzer."""

import json
import logging
import re
import sys
from pathlib import Path

from .bounce_parser import extract_bounces
from .cache import ProcessedCache
from .imap_client import ImapClient
from .ollama_client import OllamaClient
from .report import write_reports
from ..utils.categories import VALID_CATEGORIES, TARGET_CATEGORIES, is_excluded_category
from ..utils.date_utils import parse_date_or_today
from ..utils.email_utils import compute_message_hash

logger = logging.getLogger(__name__)

_RE_REPORT_FILE = re.compile(r"^\d{8}_(.+)_(target|excluded)\.json$")


def run_main(config, days):
    """Execute the main IMAP fetch-classify-report workflow for all accounts.

    Parameters
    ----------
    config : AppConfig
        Application configuration.
    days : int
        Number of days to fetch.
    """
    ollama = OllamaClient(config.ollama.base_url, config.ollama.model)
    all_summaries = {}
    for account_name, account_config in config.accounts.items():
        logger.debug("--- Processing account: %s ---", account_name)
        summary = _process_account(account_name, account_config, days, ollama, config.log_dir)
        if summary:
            all_summaries[account_name] = summary

    logger.debug("All accounts processed.")
    _log_summary(all_summaries)


def run_cleanup(config, date_text):
    """Delete report JSON files and cache entries for the given date."""
    try:
        target_date = parse_date_or_today(date_text)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    date_str = target_date.strftime("%Y%m%d")
    log_dir = Path(config.log_dir)

    # Delete report JSON files matching the date prefix
    deleted_files = 0
    for suffix in ("target", "excluded"):
        for path in log_dir.glob(f"{date_str}_*_{suffix}.json"):
            path.unlink()
            logger.info("Deleted %s", path)
            deleted_files += 1

    if not deleted_files:
        logger.info("No report files found for %s", date_str)

    # Remove matching cache entries for each account
    cache_dir = log_dir / "cache"
    total_removed = 0
    for account_name in config.accounts:
        cache = ProcessedCache(str(cache_dir), account_name)
        removed = cache.remove_entries_by_date(target_date)
        total_removed += removed
        if removed:
            cache.save()

    if not total_removed:
        logger.info("No cache entries found for %s", target_date.isoformat())

    logger.info(
        "Cleanup complete: %d file(s) deleted, %d cache entry(ies) removed.",
        deleted_files,
        total_removed,
    )


def run_report(config, date_text, category_text):
    """Read report JSON files for the given date and print a summary."""
    try:
        target_date = parse_date_or_today(date_text)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # Resolve requested categories
    if category_text:
        categories = {c.strip() for c in category_text.split(",")}
        invalid = categories - VALID_CATEGORIES
        if invalid:
            logger.error("Unknown category: %s", ", ".join(sorted(invalid)))
            logger.error("Valid categories: %s", ", ".join(sorted(VALID_CATEGORIES)))
            sys.exit(1)
    else:
        categories = TARGET_CATEGORIES

    date_str = target_date.strftime("%Y%m%d")
    log_dir = Path(config.log_dir)

    # Collect report files for the date, grouped by account
    report_files = sorted(log_dir.glob(f"{date_str}_*_*.json"))
    if not report_files:
        print(f"No report files found for {target_date.isoformat()}")
        return

    total_shown = 0
    for report_path in report_files:
        match = _RE_REPORT_FILE.match(report_path.name)
        if not match:
            continue

        try:
            with open(report_path, encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", report_path, exc)
            continue

        filtered = [r for r in records if r.get("ai_responsible_party") in categories]
        if not filtered:
            continue

        # Show path relative to cwd when possible
        try:
            rel_path = report_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = report_path
        print(rel_path)

        for i, rec in enumerate(filtered):
            if i > 0:
                print()
            print(f"  {rec.get('error_code', '')} {rec.get('error_message', '')}")
            print(f"  {rec.get('ai_responsible_party', '')}")
            print(f"  {rec.get('ai_reason', '')}")

        total_shown += len(filtered)
        print()

    if not total_shown:
        print(f"No matching records for {target_date.isoformat()} " f"(categories: {', '.join(sorted(categories))})")


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _process_account(account_name, account_config, days, ollama, log_dir):
    """Fetch bounces for a single IMAP account, classify, and write reports.

    Returns
    -------
    dict[str, int]
        Count of all bounce records grouped by ``ai_responsible_party``.
    """
    cache = ProcessedCache(f"{log_dir}/cache", account_name)
    cache.purge_older_than(days)

    client = ImapClient(account_config)
    try:
        client.connect()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.error("Failed to connect to account '%s'", account_name, exc_info=True)
        return {}

    target_records = []
    excluded_records = []
    processed_count = 0

    try:
        for folder in account_config.check:
            messages = client.fetch_messages(folder, days)
            for msg in messages:
                msg_hash = compute_message_hash(msg)
                if cache.is_processed(msg_hash):
                    continue

                bounces = extract_bounces(msg, folder=folder, sender_address=account_config.username)
                if not bounces:
                    cache.mark_processed(msg_hash)
                    continue

                for bounce in bounces:
                    classification = ollama.classify_error(bounce)
                    label = "excluded" if classification["is_excluded"] else "target"
                    logger.debug(
                        "5xx [%s] %s -> %s",
                        bounce.error_code,
                        label,
                        bounce.to_addr,
                    )
                    record = _build_record(bounce, classification)

                    if classification["is_excluded"]:
                        excluded_records.append(record)
                    else:
                        target_records.append(record)

                cache.mark_processed(msg_hash)
                processed_count += 1
    finally:
        client.disconnect()
        cache.save()

    write_reports(log_dir, account_name, target_records, excluded_records)

    logger.info(
        "Account '%s': %d bounce(s) processed, %d target, %d excluded (user)",
        account_name,
        processed_count,
        len(target_records),
        len(excluded_records),
    )

    summary = {}
    for rec in target_records + excluded_records:
        party = rec["ai_responsible_party"]
        summary[party] = summary.get(party, 0) + 1
    return summary


def _build_record(bounce, classification):
    """Merge bounce data and AI classification into a flat dict for reporting."""
    return {
        "date": bounce.date,
        "folder": bounce.folder,
        "error_code": bounce.error_code,
        "error_message": bounce.error_message,
        "ai_responsible_party": classification["responsible"],
        "ai_reason": classification["reason"],
        "from_addr": bounce.from_addr,
        "to_addr": bounce.to_addr,
        "subject": bounce.subject,
        "body_plain": bounce.body_plain,
        "body_html": bounce.body_html,
        "body_plain_original": bounce.body_plain_original,
        "body_html_original": bounce.body_html_original,
        "delivery_status": bounce.delivery_status,
    }


def _log_summary(all_summaries):
    """Log a summary of bounce record counts per account and responsible party."""
    if not all_summaries:
        logger.info("No bounce records found across all accounts.")
        return

    has_target = False
    logger.info("=== Bounce record summary ===")
    grand_total = 0
    for account_name, summary in all_summaries.items():
        parts = [f"{party}: {count}" for party, count in sorted(summary.items())]
        account_total = sum(summary.values())
        grand_total += account_total
        logger.info("  %s: %s (total: %d)", account_name, ", ".join(parts), account_total)
        if any(not is_excluded_category(p) for p in summary):
            has_target = True
    if len(all_summaries) > 1:
        logger.info("  Grand total: %d", grand_total)

    if has_target:
        logger.info("Tip: imap-error-mail-analyzer --report")
