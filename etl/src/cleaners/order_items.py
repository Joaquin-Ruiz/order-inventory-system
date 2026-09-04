"""Cleaning of order-item rows.

The database constrains each order to a single row per product
(``@@unique([orderId, productId])``), mirroring how the API aggregates
quantities by ``(order, product)`` when it builds an order. Because a product
can appear multiple times across the several CARGAs of one order, item rows are
aggregated by ``(order_number, sku)``: quantities are summed and the unit price
is carried over from the most recent occurrence.
"""

from __future__ import annotations

from typing import Dict, List, Tuple


def clean_order_items(items: List[Dict]) -> List[Dict]:
    """Return aggregated item records keyed by ``(order_number, sku)``."""
    agg: Dict[Tuple[str, str], Dict] = {}
    for it in items:
        key = (it["order_number"], it["sku"])
        existing = agg.get(key)
        if existing is None:
            agg[key] = {
                "order_number": it["order_number"],
                "sku": it["sku"],
                "quantity": int(it["quantity"]),
                "unit_price": float(it["unit_price"]),
            }
        else:
            existing["quantity"] += int(it["quantity"])
            existing["unit_price"] = float(it["unit_price"])
    return list(agg.values())
