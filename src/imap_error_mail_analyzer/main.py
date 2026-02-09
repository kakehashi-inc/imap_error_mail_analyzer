"""CLI entry point for IMAP Error Mail Analyzer."""

import argparse
import logging
import sys

from .modules.config import load_config
from .modules.imap_client import ImapClient
from .modules.bounce_parser import extract_bounces
from .modules.ollama_client import OllamaClient
from .modules.report import write_reports
from .modules.cache import ProcessedCache
from .utils.email_utils import compute_message_hash

logger = logging.getLogger(__name__)

_DEFAULT_DAYS = 30


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="imap-error-mail-analyzer",
        description="Analyze IMAP bounce mails, classify 5xx errors with Ollama, and generate CSV reports.",
    )
    parser.add_argument("-c", "--config", default="config.json", help="Path to config JSON file (default: config.json)")
    parser.add_argument("--days", type=int, default=None, help="Override fetch days (default: value from config)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    return parser.parse_args(argv)


def process_account(account_name, account_config, days, ollama, log_dir):
    """Fetch bounces for a single IMAP account, classify, and write reports.

    Returns
    -------
    dict[str, int]
        Count of target records grouped by ``ai_responsible_party``.
    """
    cache = ProcessedCache(f"{log_dir}/.cache", account_name)
    cache.purge_older_than(days)

    client = ImapClient(account_config)
    try:
        client.connect()
    except Exception:
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
                    label = "excluded" if classification["is_user_caused"] else "target"
                    logger.debug("5xx [%s] %s -> %s", bounce.error_code, label, bounce.to_addr)
                    record = _build_record(bounce, classification)

                    if classification["is_user_caused"]:
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

    target_summary = {}
    for rec in target_records:
        party = rec["ai_responsible_party"]
        target_summary[party] = target_summary.get(party, 0) + 1
    return target_summary


def _build_record(bounce, classification):
    """Merge bounce data and AI classification into a flat dict for CSV."""
    return {
        "date": bounce.date,
        "folder": bounce.folder,
        "error_code": bounce.error_code,
        "error_cause": bounce.error_message,
        "ai_responsible_party": classification["responsible"],
        "ai_reason": classification["reason"],
        "from_addr": bounce.from_addr,
        "to_addr": bounce.to_addr,
        "subject": bounce.subject,
        "body_plain": bounce.body_plain,
        "body_html": bounce.body_html,
    }


def _log_target_summary(all_summaries):
    """Log a summary of target record counts per account and responsible party."""
    if not all_summaries:
        logger.info("No target records found across all accounts.")
        return

    logger.info("=== Target record summary ===")
    grand_total = 0
    for account_name, summary in all_summaries.items():
        parts = [f"{party}: {count}" for party, count in sorted(summary.items())]
        account_total = sum(summary.values())
        grand_total += account_total
        logger.info("  %s: %s (total: %d)", account_name, ", ".join(parts), account_total)
    if len(all_summaries) > 1:
        logger.info("  Grand total: %d", grand_total)


def main():
    """Application entry point."""
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    config = load_config(args.config)
    days = args.days or config.default_days or _DEFAULT_DAYS
    logger.debug("Fetch window: %d day(s)", days)

    ollama = OllamaClient(config.ollama.base_url, config.ollama.model)

    all_summaries = {}
    for account_name, account_config in config.accounts.items():
        logger.debug("--- Processing account: %s ---", account_name)
        summary = process_account(account_name, account_config, days, ollama, config.log_dir)
        if summary:
            all_summaries[account_name] = summary

    logger.debug("All accounts processed.")
    _log_target_summary(all_summaries)


if __name__ == "__main__":
    sys.exit(main())
