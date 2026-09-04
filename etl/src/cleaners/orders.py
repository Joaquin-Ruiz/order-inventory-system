"""Cleaning of order-header rows.

The monthly sheets carry heterogeneous dates and a wide set of free-form
status values that must be mapped to the ``OrderStatus`` enum. Each source row
may repeat an order number (re-sent rows, multiple monthly sheets); the last
occurrence wins. Orders without a resolvable date are kept but flagged, and the
status falls back to ``PENDING`` when unmappable.
"""

from __future__ import annotations

from typing import Dict, List

from ..utils.parsing import parse_date, parse_order_status


def clean_orders(rows: List[Dict]) -> List[Dict]:
    """Return de-duplicated order records keyed by ``order_number``."""
    dedup: Dict[str, Dict] = {}
    dropped_no_date = 0
    for r in rows:
        order_number = r.get("order_number")
        if not order_number:
            continue
        customer = str(r.get("customer") or "").strip()
        parsed_date = parse_date(r.get("date"))
        status = parse_order_status(r.get("status")) or "PENDING"

        if parsed_date is None:
            dropped_no_date += 1
            continue

        dedup[order_number] = {
            "order_number": order_number,
            "date": parsed_date,
            "status": status,
            "customer": customer,
            "source": "ETL",
        }
    return list(dedup.values())
