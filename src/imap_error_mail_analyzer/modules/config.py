"""Configuration loading and validation."""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Ollama API connection settings."""

    base_url: str = "http://localhost:11434"
    model: str = "gemma3:4b"


@dataclass
class AccountConfig:
    """Single IMAP account connection settings."""

    name: str
    host: str
    port: int
    username: str
    password: str
    security: str = "ssl"
    check: list[str] = field(default_factory=lambda: ["INBOX"])


@dataclass
class AppConfig:
    """Application configuration."""

    default_days: int | None
    log_dir: str
    report_dir: str
    ollama: OllamaConfig
    accounts: dict[str, AccountConfig]


def load_config(config_path):
    """Load and validate configuration from a JSON file.

    Exits the process if the config file is missing or invalid.
    """
    path = Path(config_path).resolve()
    if not path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config_dir = path.parent

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    ollama_raw = raw.get("ollama", {})
    ollama = OllamaConfig(
        base_url=ollama_raw.get("base_url", "http://localhost:11434"),
        model=ollama_raw.get("model", "gemma3:4b"),
    )

    accounts = {}
    required_fields = ("host", "port", "username", "password")
    for name, acc_raw in raw.get("accounts", {}).items():
        for key in required_fields:
            if key not in acc_raw:
                logger.error("Account '%s' missing required field: %s", name, key)
                sys.exit(1)
        accounts[name] = AccountConfig(
            name=name,
            host=acc_raw["host"],
            port=acc_raw["port"],
            username=acc_raw["username"],
            password=acc_raw["password"],
            security=acc_raw.get("security", "ssl"),
            check=acc_raw.get("check", ["INBOX"]),
        )

    if not accounts:
        logger.error("No accounts configured")
        sys.exit(1)

    log_dir = config_dir / raw.get("log_dir", "logs")
    report_dir = config_dir / raw.get("report_dir", "reports")

    return AppConfig(
        default_days=raw.get("default_days"),
        log_dir=str(log_dir),
        report_dir=str(report_dir),
        ollama=ollama,
        accounts=accounts,
    )
