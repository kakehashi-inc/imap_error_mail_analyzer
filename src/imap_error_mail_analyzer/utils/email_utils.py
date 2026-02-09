"""Email parsing utilities."""

import hashlib
import re
from html.parser import HTMLParser

from email.header import decode_header as _decode_header
from email.utils import parseaddr


def decode_header_value(value):
    """Decode a MIME-encoded email header value."""
    if not value:
        return ""
    decoded_parts = []
    for part, charset in _decode_header(value):
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                decoded_parts.append(part.decode(charset, errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded_parts.append(part.decode("utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return " ".join(decoded_parts)


def get_header(msg, name, default=""):
    """Get a decoded header value from an email message."""
    raw = msg.get(name, default)
    return decode_header_value(raw)


def get_address(msg, name):
    """Extract the email address portion from a header."""
    raw = get_header(msg, name)
    _, addr = parseaddr(raw)
    return addr


def get_body_text(msg):
    """Extract plain text body from an email message.

    Walks multipart messages to find the first text/plain part.
    Falls back to decoding the payload directly for non-multipart messages.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return _decode_payload(part, payload)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return _decode_payload(msg, payload)
    return ""


def get_all_body_text(msg):
    """Extract text from both text/plain and text/html parts.

    For text/html parts, HTML tags are stripped to produce plain text.
    Returns the concatenation of all text content found in the message.
    """
    texts = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            decoded = _decode_payload(part, payload)
            if content_type == "text/plain":
                texts.append(decoded)
            elif content_type == "text/html":
                texts.append(strip_html_tags(decoded))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = _decode_payload(msg, payload)
            if msg.get_content_type() == "text/html":
                texts.append(strip_html_tags(decoded))
            else:
                texts.append(decoded)
    return "\n".join(texts)


def get_body_parts(msg):
    """Extract text/plain and text/html body content separately.

    Returns
    -------
    tuple[str, str]
        ``(plain_text, html_text)`` where html_text has tags stripped.
    """
    plains = []
    htmls = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            decoded = _decode_payload(part, payload)
            if content_type == "text/plain":
                plains.append(decoded)
            elif content_type == "text/html":
                htmls.append(strip_html_tags(decoded))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = _decode_payload(msg, payload)
            if msg.get_content_type() == "text/html":
                htmls.append(strip_html_tags(decoded))
            else:
                plains.append(decoded)
    return "\n".join(plains), "\n".join(htmls)


def strip_html_tags(html):
    """Remove HTML tags and return plain text content."""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def compute_message_hash(msg):
    """Compute a stable hash for deduplication.

    Uses Message-ID when available; otherwise falls back to a SHA-256 of
    key headers and the first 200 characters of the body.
    """
    msg_id = get_header(msg, "Message-ID").strip()
    if msg_id:
        return hashlib.sha256(msg_id.encode("utf-8")).hexdigest()

    date_val = get_header(msg, "Date")
    from_val = get_address(msg, "From")
    subject_val = get_header(msg, "Subject")
    body_val = get_body_text(msg)[:200]
    content = f"{date_val}|{from_val}|{subject_val}|{body_val}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text converter using stdlib HTMLParser."""

    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        """Return concatenated text content."""
        text = " ".join(self._parts)
        return re.sub(r"\s+", " ", text).strip()


def _decode_payload(part, payload):
    """Decode a byte payload using the part's charset."""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")
