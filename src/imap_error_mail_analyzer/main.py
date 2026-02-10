"""CLI entry point for IMAP Error Mail Analyzer."""

import argparse
import logging
import sys
from importlib.metadata import version as pkg_version

from .modules.cli import run_cleanup, run_main, run_report
from .modules.config import load_config

logger = logging.getLogger(__name__)

_DEFAULT_DAYS = 30


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="imap-error-mail-analyzer",
        description="Analyze IMAP bounce mails, classify 5xx errors with Ollama, and generate JSON reports.",
        allow_abbrev=False,
    )
    parser.add_argument("-c", "--config", default="config.json", help="Path to config JSON file (default: config.json)")
    parser.add_argument("-V", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("-v", "--version", action="version", version=pkg_version("imap-error-mail-analyzer"))

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    sub_run = subparsers.add_parser("run", help="Fetch bounces, classify, and generate reports")
    sub_run.add_argument("--days", type=int, default=None, help="Override fetch days (default: value from config)")

    # --- cleanup ---
    sub_cleanup = subparsers.add_parser("cleanup", help="Delete reports and cache entries for a date")
    sub_cleanup.add_argument("date", nargs="?", default="", metavar="DATE", help="Target date (default: today)")

    # --- report ---
    sub_report = subparsers.add_parser("report", help="Show report for a date")
    sub_report.add_argument("date", nargs="?", default="", metavar="DATE", help="Target date (default: today)")
    sub_report.add_argument(
        "--category",
        default=None,
        metavar="CATS",
        help="Categories to include (comma-separated, default: target categories)",
    )
    sub_report.add_argument(
        "--accounts",
        default=None,
        metavar="ACCTS",
        help="Account names to include (comma-separated, default: all)",
    )
    sub_report.add_argument(
        "--detail",
        action="store_true",
        help="Show body content for each record",
    )

    # --- version ---
    subparsers.add_parser("version", help="Show version")

    return parser.parse_args(argv)


def main():
    """Application entry point."""
    args = parse_args()
    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s" if args.verbose else "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=log_fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    config = load_config(args.config)

    if args.command == "cleanup":
        run_cleanup(config, args.date)
        return

    if args.command == "report":
        run_report(config, args.date, args.category, args.accounts, args.detail)
        return

    if args.command == "version":
        print(pkg_version("imap-error-mail-analyzer"))
        return

    if args.command == "run":
        days = args.days or config.default_days or _DEFAULT_DAYS
        logger.debug("Fetch window: %d day(s)", days)
        run_main(config, days)
        return


if __name__ == "__main__":
    sys.exit(main())
