"""Ollama API client for classifying email delivery errors."""

import json
import logging

import requests

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are an email delivery error analyst.
Analyze the following 5xx SMTP delivery error and determine who should handle it.

Error Code: {error_code}
Error Message: {error_message}
Failed Recipient: {to_addr}

Classify into exactly ONE of the following categories:
- "server_admin"  : Server infrastructure (disk full, service down, misconfiguration, TLS/certificate)
- "service_admin" : Service policy (sending limits, blocked domain, account disabled, spam filter)
- "other_admin"   : DNS, relay, network, or other administrative issues
- "user"          : Wrong address, nonexistent mailbox, mailbox full, user input error

Respond with ONLY a JSON object (no markdown):
{{"responsible": "<category>", "reason": "<brief reason in Japanese>"}}"""

_VALID_CATEGORIES = {"server_admin", "service_admin", "other_admin", "user"}
_USER_CATEGORIES = {"user"}


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
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=120,
            )
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")
            return _parse_response(raw_text)
        except requests.RequestException as exc:
            logger.warning("Ollama request failed: %s", exc)
            return _fallback()
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse Ollama response: %s", exc)
            return _fallback()


def _parse_response(raw_text):
    """Parse the JSON classification from Ollama's response text."""
    data = json.loads(raw_text)
    responsible = data.get("responsible", "").lower().strip()
    reason = data.get("reason", "")

    if responsible not in _VALID_CATEGORIES:
        logger.warning("Unknown category '%s', falling back", responsible)
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
