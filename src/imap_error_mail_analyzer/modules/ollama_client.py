"""Ollama API client for classifying email delivery errors."""

import logging
import re

import requests

logger = logging.getLogger(__name__)

_MAX_BODY_PROMPT_LEN = 1000

_PROMPT_TEMPLATE = """\
You are an email delivery error analyst.
Analyze the following 5xx SMTP delivery error and classify it.

Error Code: {error_code}
Error Message: {error_message}
Failed Recipient: {to_addr}

<body block>
{body}
</body block>

Classify into exactly ONE of the following categories:
- ip_block : Sending server IP/host blocked on blocklist (Spamhaus, RBL, DNSBL, blacklist)
- domain_block : Sending domain blocked or rejected by recipient policy
- rate_limit : Sending rate/volume limits exceeded, spam throttling, too many connections
- server_error : Sending server down, disk full, TLS/certificate issues, internal server error
- config_error : DNS misconfiguration (SPF/DKIM/DMARC), relay denied, network/routing problems
- user_unknown : Wrong/nonexistent recipient address, recipient domain typo or not found
- user_mailbox_full : Recipient mailbox over quota / storage full

IMPORTANT classification rules:
Block types (by priority):
1. If the SENDING SERVER IP or HOST is blocked (e.g. "Client host blocked", Spamhaus, RBL, DNSBL) -> ip_block
2. If a SENDING DOMAIN is blocked or rejected by policy -> domain_block
3. If a specific EMAIL ADDRESS is rejected or unknown -> user_unknown

DNS / domain resolution errors:
- "Host or domain name not found", "Name service error", "domain not found" for the RECIPIENT domain -> user_unknown (the sender typed a wrong domain, e.g. "yhoo.co.jp" instead of "yahoo.co.jp")
- SPF/DKIM/DMARC failures on the SENDING side -> config_error

Reply in exactly two lines (no other text):
CATEGORY: <category>
REASON: <brief reason in Japanese>"""

_VALID_CATEGORIES = {
    "ip_block",
    "domain_block",
    "rate_limit",
    "server_error",
    "config_error",
    "user_unknown",
    "user_mailbox_full",
}
_USER_CATEGORIES = {"user_unknown", "user_mailbox_full"}

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
        body = (bounce_record.body_plain or bounce_record.body_html or "")[:_MAX_BODY_PROMPT_LEN]
        prompt = _PROMPT_TEMPLATE.format(
            error_code=bounce_record.error_code,
            error_message=bounce_record.error_message,
            to_addr=bounce_record.to_addr,
            body=body,
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
