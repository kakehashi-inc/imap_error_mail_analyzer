"""CLI entry point for IMAP Error Mail Analyzer."""

import argparse
import logging
import sys

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
    parser.add_argument("--days", type=int, default=None, help="Override fetch days (default: value from config)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--cleanup",
        nargs="?",
        const="",
        default=None,
        metavar="DATE",
        help="Delete report JSONs and cache entries for DATE (default: today), then exit",
    )
    parser.add_argument(
        "--report",
        nargs="?",
        const="",
        default=None,
        metavar="DATE",
        help="Show report for DATE (default: today), then exit",
    )
    parser.add_argument(
        "--category",
        default=None,
        metavar="CATS",
        help="Categories to include in --report (comma-separated, default: target categories)",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    return parser.parse_args(argv)


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

    if args.cleanup is not None:
        run_cleanup(config, args.cleanup)
        return

    if args.report is not None:
        run_report(config, args.report, args.category)
        return

    days = args.days or config.default_days or _DEFAULT_DAYS
    logger.debug("Fetch window: %d day(s)", days)

    run_main(config, days)


if __name__ == "__main__":
    sys.exit(main())
