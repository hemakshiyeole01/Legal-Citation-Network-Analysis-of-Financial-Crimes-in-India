"""Small, dependency-free helpers shared by the data layer and the API."""
from __future__ import annotations

import calendar
import math
import re
from datetime import date
from typing import Any

_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_NAME_RE = re.compile(
    r"^(?P<parties>.+?)\s+on\s+(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})(?:\s+\d+)?$"
)


def stem(file_name: str) -> str:
    return re.sub(r"\.pdf$", "", file_name, flags=re.IGNORECASE)


def parse_case_name(file_name: str) -> dict[str, Any]:
    """Split an Indian Kanoon style file name into parties and decision date.

    'Mrs_Maneka_Gandhi_vs_Union_Of_India_on_25_January_1978_1.PDF'
        -> parties 'Mrs Maneka Gandhi vs Union Of India', date 1978-01-25, year 1978

    Used for cited cases that are outside the five domain corpora, which have no row in
    node_metrics.csv and therefore no stored title or year.
    """
    text = re.sub(r"\s+", " ", stem(file_name).replace("_", " ")).strip()
    match = _NAME_RE.match(text)
    if not match:
        return {"parties": text, "decision_date": None, "year": None}
    month = _MONTHS.get(match["month"].lower())
    year = int(match["year"])
    decision_date = None
    if month:
        try:
            decision_date = date(year, month, int(match["day"])).isoformat()
        except ValueError:
            decision_date = None
    return {"parties": match["parties"].strip(), "decision_date": decision_date, "year": year}


def clean_number(value: Any, digits: int | None = None) -> float | int | None:
    """NaN / inf / missing -> None so the value is valid JSON."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    if digits is not None:
        return round(number, digits)
    return int(number) if number.is_integer() else number


def decade_of(year: int) -> int:
    return (int(year) // 10) * 10


def normalize_text(text: str) -> str:
    """Lower-case and replace punctuation with spaces, for forgiving title search."""
    return re.sub(r"[^0-9a-z]+", " ", text.lower()).strip()


def short_label(text: str, limit: int = 38) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
