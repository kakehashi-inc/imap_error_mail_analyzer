"""Processed-message cache to avoid reprocessing the same bounce."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessedCache:
    """File-backed set of processed message hashes, scoped per account.

    Each entry stores the date it was added so stale entries can be purged
    when they fall outside the configured fetch window.
    """

    def __init__(self, cache_dir, account_name):
        self._dir = Path(cache_dir)
        self._path = self._dir / f"{account_name}_processed.json"
        self._data = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_processed(self, msg_hash):
        """Return True if the message hash is already in the cache."""
        return msg_hash in self._data

    def mark_processed(self, msg_hash):
        """Record *msg_hash* with today's date."""
        self._data[msg_hash] = date.today().isoformat()

    def purge_older_than(self, days):
        """Remove entries added more than *days* days ago."""
        cutoff = date.today() - timedelta(days=days)
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if date.fromisoformat(v) >= cutoff}
        removed = before - len(self._data)
        if removed:
            logger.debug("Purged %d stale cache entries", removed)

    def save(self):
        """Persist the cache to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self):
        if not self._path.exists():
            return {}
        try:
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cache %s: %s", self._path, exc)
            return {}
