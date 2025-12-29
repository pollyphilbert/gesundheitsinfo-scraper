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
        return None
