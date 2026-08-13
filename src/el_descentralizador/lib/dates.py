from datetime import datetime

MONTHS_SHORT = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


def format_short(value: datetime | None) -> str:
    if value is None:
        return ""
    return f"{value.day} {MONTHS_SHORT[value.month - 1]} {value.year}"
