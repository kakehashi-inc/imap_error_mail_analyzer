"""Date string parsing utilities."""

from datetime import date, datetime

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
