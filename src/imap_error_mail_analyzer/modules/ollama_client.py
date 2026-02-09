"""Ollama API client for classifying email delivery errors."""

import logging
import re

import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an email delivery error analyst.
Analyze the following 5xx SMTP delivery error and determine who should handle it.

Error Code: {error_code}
Error Message: {error_message}
Failed Recipient: {to_addr}

Classify into exactly ONE of the following categories:
- server_admin : Server infrastructure (disk full, service down, misconfiguration, TLS/certificate)
- service_admin : Service policy (sending limits, blocked domain, account disabled, spam filter)
- other_admin : DNS, relay, network, or other administrative issues
- user : Wrong address, nonexistent mailbox, mailbox full, user input error

Reply in exactly two lines (no other text):
CATEGORY: <category>
REASON: <brief reason in Japanese>"""

_VALID_CATEGORIES = {"server_admin", "service_admin", "other_admin", "user"}
_USER_CATEGORIES = {"user"}

_RE_CATEGORY = re.compile(r"CATEGORY\s*:\s*(\S+)", re.IGNORECASE)
_RE_REASON = re.compile(r"REASON\s*:\s*(.+)", re.IGNORECASE)


class OllamaClient:
    """Thin wrapper around the Ollama ``/api/generate`` endpoint."""

    def __init__(self, base_url, model):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._endpoint = f"{self.base_url}/api/generate"

    def test_connection(self):
        """Return True if the Ollama server is reachable and the model is available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return any(self.model in m for m in models)
        except requests.RequestException as exc:
            logger.warning("Ollama connection test failed: %s", exc)
            return False

    def classify_error(self, bounce_record):
        """Ask Ollama to classify a bounce error.

        Returns
        -------
        dict
            ``{"responsible": str, "reason": str, "is_user_caused": bool}``
        """
        prompt = _PROMPT_TEMPLATE.format(
            error_code=bounce_record.error_code,
            error_message=bounce_record.error_message,
            to_addr=bounce_record.to_addr,
        )

        try:
            resp = requests.post(
                self._endpoint,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")
            return _parse_response(raw_text)
        except requests.RequestException as exc:
            logger.warning("Ollama request failed: %s", exc)
            return _fallback()


def _parse_response(raw_text):
    """Parse the plain-text classification from Ollama's response."""
    cat_match = _RE_CATEGORY.search(raw_text)
    reason_match = _RE_REASON.search(raw_text)

    responsible = cat_match.group(1).lower().strip() if cat_match else ""
    reason = reason_match.group(1).strip() if reason_match else ""

    if responsible not in _VALID_CATEGORIES:
        logger.warning("Unknown category '%s' in response: %s", responsible, raw_text[:200])
        return _fallback(reason)

    return {
        "responsible": responsible,
        "reason": reason,
        "is_user_caused": responsible in _USER_CATEGORIES,
    }


def _fallback(reason=""):
    """Return a safe default when classification fails."""
    return {
        "responsible": "unknown",
        "reason": reason or "Classification unavailable",
        "is_user_caused": False,
    }
