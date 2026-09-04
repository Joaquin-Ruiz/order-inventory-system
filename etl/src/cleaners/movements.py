"""Cleaning of inventory-movement rows.

Movement rows are keyed by their ``external_key`` (sheet:sku:type:doc:reason)
so re-running the pipeline never duplicates rows. The type must be one of the
``InventoryMovementType`` enum values and the quantity a positive integer;
anything else is dropped.
"""

from __future__ import annotations

from typing import List

_VALID_TYPES = {"IN", "OUT", "ADJUSTMENT"}


def clean_movements(rows: List[Dict]) -> List[Dict]:
    """Return validated movement records keyed by ``external_key``."""
    cleaned = []
    for r in rows:
        mtype = r.get("type")
        if mtype not in _VALID_TYPES:
            continue
        quantity = int(r.get("quantity") or 0)
        if quantity <= 0:
            continue
        if not r.get("movement_date"):
            continue
        if not r.get("external_key"):
            continue
        cleaned.append(
            {
                "sku": r["sku"],
                "type": mtype,
                "quantity": quantity,
                "reason": (r.get("reason") or None),
                "document": (r.get("document") or None),
                "movement_date": r["movement_date"],
                "source": "ETL",
                "external_key": r["external_key"],
            }
        )
    return cleaned
