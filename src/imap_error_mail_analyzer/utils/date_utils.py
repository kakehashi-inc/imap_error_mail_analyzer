"""Date string parsing utilities."""

from datetime import date, datetime
from email.utils import parsedate_to_datetime

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
)


def parse_date(text):
    """Parse a date string in yyyy-MM-dd, yyyy/MM/dd, or yyyyMMdd format.

    Returns
    -------
    datetime.date

    Raises
    ------
    ValueError
        If *text* does not match any supported format.
    """
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: '{text}'. " f"Expected yyyy-MM-dd, yyyy/MM/dd, or yyyyMMdd.")


def parse_date_or_today(text):
    """Parse a date string, defaulting to today when *text* is empty or None.

    Returns
    -------
    datetime.date
    """
    if not text:
        return date.today()
    return parse_date(text)


def format_email_date(raw_date):
    """Format an RFC 2822 email Date header as local time ``yyyy-MM-dd HH:mm:ss``.

    Parameters
    ----------
    raw_date : str
        Raw ``Date`` header value (e.g. ``Mon, 10 Feb 2026 12:34:56 +0900``).

    Returns
    -------
    str
        Formatted local-time string, or *raw_date* unchanged on parse failure.
    """
    if not raw_date:
        return ""
    try:
        dt = parsedate_to_datetime(raw_date)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return raw_date
