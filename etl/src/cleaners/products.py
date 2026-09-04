"""Cleaning of product rows.

The catalog mixes net and IVA-inclusive prices across families: the ``HOGAR``
sheet states its prices are expressed *CON IVA INCLUIDO (19%)*, while every
other family is net. Products are keyed by canonical SKU; when the same SKU
appears more than once the last occurrence (i.e. the newest published value)
wins.
"""

from __future__ import annotations

from typing import Dict, List

# Chilean IVA rate for normalising the HOGAR row (prices include IVA).
_IVA_RATE = 0.19


def _net_price(price: float, family: str) -> float:
    """Strip IVA from a HOGAR list price so all prices are net units."""
    if family.upper() != "HOGAR":
        return round(price, 2)
    return round(price / (1 + _IVA_RATE), 2)


def clean_products(rows: List[Dict]) -> List[Dict]:
    """Return de-duplicated, normalised product records keyed by SKU."""
    dedup: Dict[str, Dict] = {}
    for r in rows:
        sku = r["sku"]
        if not sku:
            continue
        price = _net_price(float(r.get("price") or 0), str(r.get("family") or ""))
        stock = int(r.get("stock") or 0)
        if stock < 0:
            stock = 0
        dedup[sku] = {
            "sku": sku,
            "name": str(r.get("name") or "").strip(),
            "stock": stock,
            "price": price,
            "active": bool(r.get("active", True)),
            "family": str(r.get("family") or ""),
        }
    return list(dedup.values())
