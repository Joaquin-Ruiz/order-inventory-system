"""Utility functions shared by the ETL pipeline."""

from .normalize import looks_like_sku, normalize_sku

__all__ = ["looks_like_sku", "normalize_sku"]
