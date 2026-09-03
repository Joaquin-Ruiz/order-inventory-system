"""Normalization helpers shared across the ETL pipeline.

These functions intentionally mirror the business rules used by the API
(NestJS ``normalizeSku``) so that data integrated from the periodic Excel
files lands on the *same* rows as data coming from the real-time API.
"""

from __future__ import annotations

import re
from typing import Union

# Matches a bare prefix + number, e.g. "FER10" -> "FER-0010".
_SKU_SPLIT_RE = re.compile(r"^([A-Z]{1,6})(\d{1,6})$", re.IGNORECASE)


def normalize_sku(value: Union[str, object]) -> str:
    """Normalize a raw SKU to the canonical ``PREFIX-0000`` form.

    Behaviour (aligned with the API):
      1. Trim surrounding whitespace.
      2. Uppercase and keep only letters and digits.
      3. If the result is ``PREFIX + digits`` pad the digits to 4 and join
         with a hyphen (``FER-10`` -> ``FER-0010``). Otherwise return the
         cleaned value unchanged (e.g. unknown/blank input).
    """
    if value is None:
        return ""

    text = str(value).strip().upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", text)

    match = _SKU_SPLIT_RE.match(cleaned)
    if not match:
        return cleaned

    prefix = match.group(1)
    number = str(int(match.group(2)))
    return f"{prefix}-{number.zfill(4)}"


def looks_like_sku(value: object) -> bool:
    """Return True when a value plausibly maps to a canonical SKU.

    Used to discard stray filler rows (descriptions, ``SIN CODIGO``, ``ZZZ``,
    ``XXX``, totals, blank lines, ...) that sneak into SKU columns.
    """
    sku = normalize_sku(value)
    return bool(re.fullmatch(r"[A-Z]{1,6}-\d{4}", sku))
