"""Parsing helpers for messy Excel content.

The source Excel files use a mix of:
  * date formats (``2026-01-19``, ``03.01.2026``, ``06-ene-26``,
    ``18 de enero de 2026``, ``19 de mar de 26``, Excel serials, real
    ``datetime`` objects);
  * number formats (``18.020``, ``2.020,00``, ``$ 38.640``, ``920,00``,
    ``$18.020.-``);
  * quantities carrying their unit ("2 un", "24 un", "-", "10,0").
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Union

from datetime import timedelta

from dateutil import parser as date_parser

# Spanish month names -> lowercase key for normalizing textual dates.
_MONTHS_PT = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

def _month_number(token: str) -> Optional[int]:
    token = token.lower().strip()
    # "mar" matches marzo; "abr" -> abril; "sep" -> septiembre; ...
    for idx, name in enumerate(_MONTHS_PT, start=1):
        if name.startswith(token):
            return idx
    return None


def _is_excel_serial(value: Union[int, float, str]) -> Optional[date]:
    """Excel stores dates as day-of-epoch serials when the cell is numeric."""
    try:
        num = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if num <= 0 or num > 100000:
        return None
    try:
        return (datetime(1899, 12, 30) + timedelta(days=num)).date()
    except (OverflowError, ValueError, TypeError):
        return None


def parse_date(value: object) -> Optional[date]:
    """Parse a heterogeneous date value into a ``date`` (or ``None``)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Numeric Excel serial -> real date.
    serial = _is_excel_serial(text)
    if serial is not None:
        return serial

    # Replace Spanish months so dateutil understands "ene" -> January.
    normalized = text
    for name in _MONTHS_PT:
        normalized = re.sub(rf"\b{name[:3]}", name, normalized, flags=re.IGNORECASE)

    # Explicit Spanish day-month-year form: "14-abr-26", "28 de abr de 26",
    # "9 de may de 26", "14-04-2026". Handles 2- or 4-digit years.
    parsed = _parse_spanish_date(text)
    if parsed is not None:
        return parsed

    try:
        return date_parser.parse(normalized, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


# Matches a Spanish day-month-year date: "14-abr-26", "28 de abr de 26",
# "9 de may de 26", "03-may-26", "14-04-2026".
_SPANISH_DATE_RE = re.compile(
    r"^\s*"
    r"(?P<day>\d{1,2})"
    r"(?:\s*de\s+|\s+|-|/)(?P<month>\d{1,2}|[A-Za-z]+)"
    r"(?:\s*de\s+|\s+|-|/)(?P<year>\d{2,4})"
    r"\s*$",
)


def _parse_spanish_date(text: str):
    """Parse a Spanish ``DD MMM YY`` date, returning a ``date`` or ``None``."""
    m = _SPANISH_DATE_RE.match(text.strip())
    if not m:
        return None
    day = int(m.group("day"))
    year = int(m.group("year"))
    ym = m.group("month")
    if ym.isdigit():
        month = int(ym)
    else:
        month = _month_number(ym)
        if month is None:
            return None
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:  # impossible date, e.g. 31-04-2026
        return None


def _to_clean_float(token: str) -> Optional[float]:
    t = token.strip()
    if not t:
        return None
    # Strip currency symbols and trailing dots/decoration ("$18.020.-").
    t = re.sub(r"[$\s]", "", t)
    t = re.sub(r"\.-$", "", t)
    t = t.rstrip(".-")
    if not t:
        return None
    # European style: "2.020,00" -> 2020.00 ; "920,00" -> 920.00
    # "21.710" (no decimal comma) -> 21710
    # "18.020" -> 18020 ; "1.915,00" -> 1915.00
    if "," in t and "." in t:
        # Both: treat '.' as thousands separator and ',' as decimal.
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        # Only comma: if it looks like thousands (e.g. "10,000" -> 10000).
        if re.match(r"^\d{1,3}(,\d{3})+$", t):
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")
    elif "." in t:
        # Only dot: could be thousands separator or decimal.
        # A single dot followed by exactly 3 digits is the Chilean thousands
        # format ("5.260" -> 5260). Prices here are integer amounts, so any
        # "N.NNN" with a dot and three trailing digits is a thousands group.
        if re.fullmatch(r"\d{1,3}\.\d{3}", t):
            t = t.replace(".", "")
        # otherwise keep as-is (plain integer-like or decimal).
    try:
        return float(t)
    except ValueError:
        return None


def parse_number(value: object) -> Optional[float]:
    """Parse a messy numeric value (currency, thousands, decimals) to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    return _to_clean_float(text)


def parse_int(value: object) -> Optional[int]:
    """Parse a number/quantity into a non-negative int, or ``None``."""
    num = parse_number(value)
    if num is None:
        return None
    try:
        return int(round(num))
    except (ValueError, OverflowError):
        return None


_QTY_RE = re.compile(r"(-?[\d.,]+)\s*(?:un|UN|c/u|cada|UND|UNIDAD|unidad)*\.?", re.IGNORECASE)

def parse_quantity(value: object) -> Optional[int]:
    """Extract a quantity from cells like ``2 un``, ``24 un``, ``-``, ``10,0``."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
        return int(round(num)) if num > 0 else None
    text = str(value).strip()
    if not text or text in {"-", "—", "s/i", "s/d"}:
        return None
    m = _QTY_RE.search(text)
    if not m:
        return None
    num = parse_number(m.group(1))
    if num is None or num <= 0:
        return None
    return int(round(num))


# --- Order status normalisation (mirrors the OrderStatus enum) ------------
_STATUS = {
    "pending": "PENDING",
    "pendiente": "PENDING",
    "pend": "PENDING",
    "process": "PROCESSING",
    "proceso": "PROCESSING",
    "procesando": "PROCESSING",
    "en proceso": "PROCESSING",
    "en preparacion": "PROCESSING",
    "preparacion": "PROCESSING",
    "en_proceso": "PROCESSING",
    "despachado": "DISPATCHED",
    "despachada": "DISPATCHED",
    "desp": "DISPATCHED",
    "en ruta": "DISPATCHED",
    "ruta": "DISPATCHED",
    "entregado": "COMPLETED",
    "entregada": "COMPLETED",
    "entreg.": "COMPLETED",
    "completado": "COMPLETED",
    "completada": "COMPLETED",
    "cerrado": "COMPLETED",
    "ok": "COMPLETED",
    "cancelado": "CANCELLED",
    "cancelada": "CANCELLED",
    "anulado": "CANCELLED",
    "anulada": "CANCELLED",
    "anul": "CANCELLED",
    "nulo": "CANCELLED",
    "nula": "CANCELLED",
    "20": "PENDING",
    "40": "PROCESSING",
    "60": "COMPLETED",
}


def parse_order_status(value: object) -> Optional[str]:
    """Map a raw status string to an ``OrderStatus`` enum value."""
    if value is None:
        return None
    key = str(value).strip().lower()
    return _STATUS.get(key)
