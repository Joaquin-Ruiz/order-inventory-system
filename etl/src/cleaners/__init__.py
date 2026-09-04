"""Cleaners that turn raw reader rows into write-ready records.

A cleaner is responsible for:
  * normalising/validating each field,
  * de-duplicating (the workbook sources intentionally contain overlaps,
    corrections and re-sent rows),
  * and producing records that match the API's table shapes exactly.
"""

from .movements import clean_movements
from .order_items import clean_order_items
from .orders import clean_orders
from .products import clean_products

__all__ = [
    "clean_movements",
    "clean_order_items",
    "clean_orders",
    "clean_products",
]
