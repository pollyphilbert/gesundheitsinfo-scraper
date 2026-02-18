"""
Utility functions for parsing German date strings.

Currently supports parsing strings in format:
    "Aktualisiert am 12. März 2023"

Returns:
    datetime.date object or None if parsing fails.
"""

import datetime

GERMAN_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

def parse_german_date(text: str):
    """
    Parse German update date string into datetime.date.

    Expected formats:
        "Aktualisiert am 12. März 2023"
        "12. März 2023"

    Args:
        text (str): Raw text containing German date.

    Returns:
        datetime.date | None
    """

    if not text:
        return None

    try:
        parts = text.replace("Aktualisiert am", "").strip()
        day, month, year = parts.replace(".", "").split()

        month_num = GERMAN_MONTHS.get(month.lower())
        if not month_num:
            return None

        return datetime.date(
            int(year),
            month_num,
            int(day),
        )
    except Exception:
        # Prevents crawler from crashing on unexpected formats
        return None
