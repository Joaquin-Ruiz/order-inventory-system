"""Data-quality validation rules.

One tiny dataclass (:class:`ValidationResult`) plus four rule sets that reject
records which would violate the API's constraints: canonical SKUs, sane
quantities/prices, resolvable dates, and valid enum members.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..utils.normalize import looks_like_sku

_ORDER_STATUSES = {"PENDING", "PROCESSING", "DISPATCHED", "COMPLETED", "CANCELLED"}
_MOVEMENT_TYPES = {"IN", "OUT", "ADJUSTMENT"}


@dataclass
class ValidationResult:
    kind: str
    total: int = 0
    accepted: int = 0
    rejected: int = 0
    reasons: Dict[str, int] = field(default_factory=dict)

    def accept(self, row) -> List[Dict]:
        self.accepted += 1
        return [row]

    def reject(self, reason: str) -> List[Dict]:
        self.rejected += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1
        return []

    @property
    def summary(self) -> Dict:
        return {
            "kind": self.kind,
            "total": self.total,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "reasons": dict(self.reasons),
        }


def _validate(rows: List[Dict], kind: str, check) -> ValidationResult:
    res = ValidationResult(kind=kind, total=len(rows))
    for row in rows:
        reason = check(row)
        if reason is None:
            res.accept(row)
        else:
            res.reject(reason)
    return res


def validate_products(rows: List[Dict]) -> ValidationResult:
    def check(r):
        if not r.get("sku") or not looks_like_sku(r["sku"]):
            return "invalid_sku"
        if not (r.get("name") or "").strip():
            return "missing_name"
        if (r.get("price") is None) or float(r["price"]) < 0:
            return "invalid_price"
        return None

    return _validate(rows, "products", check)


def validate_orders(rows: List[Dict]) -> ValidationResult:
    def check(r):
        if not r.get("order_number"):
            return "missing_order_number"
        if r.get("status") not in _ORDER_STATUSES:
            return "invalid_status"
        if r.get("date") is None:
            return "invalid_date"
        return None

    return _validate(rows, "orders", check)


def validate_order_items(rows: List[Dict]) -> ValidationResult:
    def check(r):
        if not r.get("order_number") or not r.get("sku"):
            return "missing_key"
        if not looks_like_sku(r["sku"]):
            return "invalid_sku"
        if (r.get("quantity") is None) or int(r["quantity"]) <= 0:
            return "invalid_quantity"
        if (r.get("unit_price") is None) or float(r["unit_price"]) <= 0:
            return "invalid_price"
        return None

    return _validate(rows, "order_items", check)


def validate_movements(rows: List[Dict]) -> ValidationResult:
    def check(r):
        if r.get("type") not in _MOVEMENT_TYPES:
            return "invalid_type"
        if (r.get("quantity") is None) or int(r["quantity"]) <= 0:
            return "invalid_quantity"
        if r.get("movement_date") is None:
            return "invalid_date"
        if not r.get("sku") or not looks_like_sku(r["sku"]):
            return "invalid_sku"
        return None

    return _validate(rows, "movements", check)
