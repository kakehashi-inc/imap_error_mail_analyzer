"""Bounce message parser for extracting 5xx delivery errors."""

import re
import logging
from dataclasses import dataclass

from ..utils.date_utils import format_email_date
from ..utils.email_utils import (
    decode_header_value,
    get_header,
    get_address,
    get_all_body_text,
    get_separated_body_parts,
    normalize_whitespace,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# DSN fields
_RE_DIAGNOSTIC = re.compile(
    r"[Dd]iagnostic-[Cc]ode\s*:\s*smtp\s*;\s*(.+?)(?:\r?\n(?!\s)|$)",
    re.MULTILINE | re.DOTALL,
)
_RE_FINAL_RECIPIENT = re.compile(
    r"[Ff]inal-[Rr]ecipient\s*:\s*(?:rfc822|RFC822)\s*;\s*(\S+)",
    re.MULTILINE,
)
_RE_ORIGINAL_RECIPIENT = re.compile(
    r"[Oo]riginal-[Rr]ecipient\s*:\s*(?:rfc822|RFC822)\s*;\s*(\S+)",
    re.MULTILINE,
)
_RE_DSN_STATUS = re.compile(
    r"[Ss]tatus\s*:\s*(5\.\d+\.\d+)",
    re.MULTILINE,
)

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

# Maximum body snippet length stored in a record
_MAX_BODY_LEN = 1000


@dataclass
class BounceRecord:  # pylint: disable=too-many-instance-attributes
    """Single 5xx bounce error extracted from a message."""

    date: str
    error_code: str
    error_message: str
    from_addr: str
    to_addr: str
    subject: str
    body_plain: str
    body_html: str
    body_plain_original: str
    body_html_original: str
    delivery_status: dict
    folder: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_bounces(msg, folder="INBOX", sender_address=""):
    """Extract 5xx bounce information from *msg*.

    All messages are inspected for 5xx errors regardless of whether they
    match traditional bounce message patterns.  DSN structured parsing is
    attempted first; if no DSN part is found the full body text (including
    HTML parts) is scanned with regex.  Messages that contain no 5xx
    errors simply return an empty list.

    Parameters
    ----------
    msg : email.message.Message
        The email message to inspect.
    folder : str
        Mailbox folder the message was fetched from.
    sender_address : str
        Fallback original-sender address (typically the account username).

    Returns
    -------
    list[BounceRecord]
        One record per failed recipient / error found.  Empty list when
        no 5xx errors are detected.
    """
    date = format_email_date(get_header(msg, "Date"))
    body_text = get_all_body_text(msg)

    # Only DSN structured parsing; body regex fallback removed (too noisy)
    errors = _extract_dsn_errors(msg)
    if not errors:
        return []

    from_addr = _extract_original_from(msg, body_text) or sender_address
    original_subject = _extract_original_subject(msg, body_text) or get_header(msg, "Subject")

    # Fill in missing recipient addresses from other sources
    failed_recipients = _extract_failed_recipients(msg, body_text)
    for i, err in enumerate(errors):
        if not err["to_addr"] and failed_recipients:
            err["to_addr"] = failed_recipients[min(i, len(failed_recipients) - 1)]

    notif_plain, notif_html, orig_plain, orig_html = get_separated_body_parts(msg)
    plain_snippet = normalize_whitespace(notif_plain)[:_MAX_BODY_LEN]
    html_snippet = normalize_whitespace(notif_html)[:_MAX_BODY_LEN]
    orig_plain_snippet = normalize_whitespace(orig_plain)[:_MAX_BODY_LEN]
    orig_html_snippet = normalize_whitespace(orig_html)[:_MAX_BODY_LEN]

    return [
        BounceRecord(
            date=date,
            error_code=err["error_code"],
            error_message=err["error_message"],
            from_addr=from_addr,
            to_addr=err["to_addr"],
            subject=original_subject,
            body_plain=plain_snippet,
            body_html=html_snippet,
            body_plain_original=orig_plain_snippet,
            body_html_original=orig_html_snippet,
            delivery_status=err.get("delivery_status", {}),
            folder=folder,
        )
        for err in errors
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_dsn_errors(msg):
    """Parse errors from a DSN (multipart/report) delivery-status part.

    Each returned dict includes a ``delivery_status`` sub-dict that
    preserves the full set of DSN fields (per-message fields merged
    with the per-recipient fields) so that no information is lost.
    """
    dsn_text = ""
    for part in msg.walk():
        if part.get_content_type() == "message/delivery-status":
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                try:
                    dsn_text = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    dsn_text = payload.decode("utf-8", errors="replace")
            elif isinstance(part.get_payload(), list):
                dsn_text = "\n".join(sub.as_string() for sub in part.get_payload() if hasattr(sub, "as_string"))
            break

    if not dsn_text:
        return []

    # Split into per-recipient sections (separated by blank lines)
    sections = re.split(r"\n\n+", dsn_text)

    # First section without a Status field is the per-message section
    per_message_fields = {}
    if sections and not _RE_DSN_STATUS.search(sections[0]):
        per_message_fields = _parse_dsn_fields(sections[0])

    results = []
    for section in sections:
        status_match = _RE_DSN_STATUS.search(section)
        if not status_match:
            continue

        recipient_match = _RE_FINAL_RECIPIENT.search(section) or _RE_ORIGINAL_RECIPIENT.search(section)
        recipient = recipient_match.group(1).strip() if recipient_match else ""

        diag_match = _RE_DIAGNOSTIC.search(section)
        diagnostic = diag_match.group(1).strip() if diag_match else ""

        error_code = ""
        error_message = diagnostic
        if diagnostic:
            code_match = re.match(r"(5\d{2})[\s\-]+(.*)", diagnostic, re.DOTALL)
            if code_match:
                error_code = code_match.group(1)
                error_message = re.sub(r"\s+", " ", code_match.group(2)).strip()
        if not error_code:
            error_code = status_match.group(1)
        if not error_message:
            error_message = f"DSN status {status_match.group(1)}"

        # Merge per-message fields with per-recipient fields
        dsn_fields = {**per_message_fields, **_parse_dsn_fields(section)}

        results.append(
            {
                "error_code": error_code,
                "error_message": error_message,
                "to_addr": recipient,
                "delivery_status": dsn_fields,
            }
        )

    return results


def _parse_dsn_fields(section):
    """Parse a DSN section into a dict of normalised field names and values.

    Field names are lowercased with hyphens replaced by underscores
    (e.g. ``Diagnostic-Code`` becomes ``diagnostic_code``).
    Continuation lines (starting with whitespace) are joined.
    """
    fields = {}
    current_key = None
    current_value = ""
    for line in section.splitlines():
        if not line or line.isspace():
            continue
        if line[0].isspace() and current_key:
            # Continuation line
            current_value += " " + line.strip()
        else:
            if current_key:
                fields[current_key] = current_value
            match = re.match(r"([A-Za-z][A-Za-z0-9\-]*):\s*(.*)", line)
            if match:
                current_key = match.group(1).lower().replace("-", "_")
                current_value = match.group(2).strip()
            else:
                current_key = None
                current_value = ""
    if current_key:
        fields[current_key] = current_value
    return fields


def _extract_failed_recipients(msg, body_text):
    """Try to determine the failed recipient address(es)."""
    x_failed = get_header(msg, "X-Failed-Recipients")
    if x_failed:
        return [addr.strip() for addr in x_failed.split(",") if addr.strip()]

    recipients = []
    for line in body_text.split("\n"):
        lower = line.lower()
        if any(kw in lower for kw in ("recipient", "rcpt to", "original-recipient", "final-recipient")):
            recipients.extend(_EMAIL_PATTERN.findall(line))

    return list(dict.fromkeys(recipients))


def _extract_original_subject(msg, body_text):
    """Try to recover the original email's Subject from the bounce."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "message/rfc822":
                payload = part.get_payload()
                if isinstance(payload, list) and payload:
                    subj = get_header(payload[0], "Subject")
                    if subj:
                        return subj

    match = re.search(r"^Subject:\s*(.+?)$", body_text, re.MULTILINE)
    if match:
        return decode_header_value(match.group(1).strip())
    return ""


def _extract_original_from(msg, body_text):
    """Try to recover the original sender address from the bounce."""
    # The bounce's To header is typically the original sender
    addr = get_address(msg, "To")
    if addr:
        return addr

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "message/rfc822":
                payload = part.get_payload()
                if isinstance(payload, list) and payload:
                    addr = get_address(payload[0], "From")
                    if addr:
                        return addr

    match = re.search(r"^From:\s*(.+?)$", body_text, re.MULTILINE)
    if match:
        raw = match.group(1).strip()
        addrs = _EMAIL_PATTERN.findall(raw)
        if addrs:
            return addrs[0]

    return ""
