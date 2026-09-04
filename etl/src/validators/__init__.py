"""Validators enforcing data-quality rules before a record is written.

Each validator inspects a list of *cleaned* records, applies domain rules and
rejects anything that violates them, returning a :class:`ValidationResult` that
captures how many rows were examined, accepted and dropped (with per-rule
counts) so the pipeline can report data-quality metrics.
"""

from .core import ValidationResult, validate_movements, validate_order_items, validate_orders, validate_products

__all__ = [
    "ValidationResult",
    "validate_movements",
    "validate_order_items",
    "validate_orders",
    "validate_products",
]
