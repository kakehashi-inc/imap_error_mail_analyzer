"""Email parsing utilities."""

import hashlib
import re

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

    For text/html parts, body content is extracted and style/script blocks
    are removed.  Returns the concatenation of all text content found.
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
                texts.append(clean_html_body(decoded))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = _decode_payload(msg, payload)
            if msg.get_content_type() == "text/html":
                texts.append(clean_html_body(decoded))
            else:
                texts.append(decoded)
    return "\n".join(texts)


def get_body_parts(msg):
    """Extract text/plain and text/html body content separately.

    Returns
    -------
    tuple[str, str]
        ``(plain_text, html_text)`` where html_text has body extracted
        and style/script removed but HTML tags preserved.
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
                htmls.append(clean_html_body(decoded))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = _decode_payload(msg, payload)
            if msg.get_content_type() == "text/html":
                htmls.append(clean_html_body(decoded))
            else:
                plains.append(decoded)
    return "\n".join(plains), "\n".join(htmls)


def get_separated_body_parts(msg):
    """Separate bounce notification body from original message body.

    Bounce emails typically contain a notification part (error information)
    and the original message inside a ``message/rfc822`` part.  This function
    collects text from each side independently so that only the error
    notification is passed to the AI classifier.

    Returns
    -------
    tuple[str, str, str, str]
        ``(notification_plain, notification_html,
          original_plain, original_html)``
    """
    notif_plains = []
    notif_htmls = []
    orig_plains = []
    orig_htmls = []

    if msg.is_multipart():
        _collect_notification_parts(msg, notif_plains, notif_htmls)
        _collect_original_parts(msg, orig_plains, orig_htmls)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = _decode_payload(msg, payload)
            if msg.get_content_type() == "text/html":
                notif_htmls.append(clean_html_body(decoded))
            else:
                notif_plains.append(decoded)

    return (
        "\n".join(notif_plains),
        "\n".join(notif_htmls),
        "\n".join(orig_plains),
        "\n".join(orig_htmls),
    )


def _collect_notification_parts(msg, plains, htmls):
    """Recursively collect text parts, skipping message/rfc822 boundaries."""
    for part in msg.get_payload():
        content_type = part.get_content_type()
        if content_type in ("message/rfc822", "message/delivery-status"):
            continue
        if part.is_multipart():
            _collect_notification_parts(part, plains, htmls)
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        decoded = _decode_payload(part, payload)
        if content_type == "text/plain":
            plains.append(decoded)
        elif content_type == "text/html":
            htmls.append(clean_html_body(decoded))


def _collect_original_parts(msg, plains, htmls):
    """Extract body from message/rfc822 parts (the original message)."""
    for part in msg.get_payload():
        if part.get_content_type() == "message/rfc822":
            inner = part.get_payload()
            if isinstance(inner, list) and inner:
                inner = inner[0]
            if inner:
                plain, html = get_body_parts(inner)
                if plain:
                    plains.append(plain)
                if html:
                    htmls.append(html)
        elif part.is_multipart():
            _collect_original_parts(part, plains, htmls)


def clean_html_body(html):
    """Clean HTML for output by extracting body content and removing noise.

    Processing steps:
    1. Extract ``<body>`` content (skip head/meta); use full HTML if no body tag.
    2. Remove ``<style>`` and ``<script>`` blocks entirely.
    """
    # Extract <body> content
    body_match = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
    text = body_match.group(1) if body_match else html

    # Remove <style> and <script> blocks
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text


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


def normalize_whitespace(text):
    """Normalize whitespace in body text for compact, readable output.

    - 2+ consecutive spaces/tabs are collapsed to a single space.
    - Lines containing only whitespace become empty lines.
    - Consecutive newlines are limited to 2 (line end + one blank line).
    """
    # Collapse 2+ horizontal whitespace characters to single space
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    # Lines with only whitespace become just a newline
    text = re.sub(r"^[ \t]+$", "", text, flags=re.MULTILINE)
    # Collapse 3+ consecutive newlines to 2 (line end + one blank line)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_payload(part, payload):
    """Decode a byte payload using the part's charset."""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")
