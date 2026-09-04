"""Tests for the readers against the bundled example workbooks."""

import re

from src.readers.catalog import read_catalog
from src.readers.details import read_details
from src.readers.movements import read_movements
from src.readers.orders import read_order_headers

SKU_RE = re.compile(r"[A-Z]{1,6}-\d{4}")


def test_catalog_reads_products(catalog_path):
    rows = read_catalog(catalog_path)
    assert len(rows) >= 90
    skus = {r["sku"] for r in rows}
    assert len(skus) == len(rows)  # no duplicate SKUs after corrections
    assert all(SKU_RE.fullmatch(r["sku"]) for r in rows)
    # Corrections applied: FER-0006 price was overridden in March.
    fer_0006 = next(r for r in rows if r["sku"] == "FER-0006")
    assert fer_0006["price"] > 10000
    # The later 28-03 correction must replace the 08-03 stock value (46).
    hog_0008 = next(r for r in rows if r["sku"] == "HOG-0008")
    assert hog_0008["stock"] == 15
    assert all("family" in r for r in rows)


def test_order_headers_read(orders_path):
    rows = read_order_headers(orders_path)
    assert len(rows) == 407
    numbers = {r["order_number"] for r in rows}
    assert len(numbers) == len(rows)  # already de-duplicated
    assert all(n.startswith("PED-") for n in numbers)
    assert "PED-1001" in numbers  # January uses the N° PEDIDO header.


def test_details_read_with_catalog(details_path, catalog_path):
    catalog = read_catalog(catalog_path)
    name_to_sku = {" ".join(str(r["name"]).lower().split()): r["sku"] for r in catalog}
    items = read_details(details_path, name_to_sku=name_to_sku)
    assert len(items) > 800
    assert all(SKU_RE.fullmatch(it["sku"]) for it in items)
    assert all(it["order_number"].startswith("PED-") for it in items)
    # CARGA 03 (description-based) resolved at least one SKU.
    assert any(it["sku"] for it in items)


def test_details_no_garbage_sku(details_path, catalog_path):
    catalog = read_catalog(catalog_path)
    name_to_sku = {" ".join(str(r["name"]).lower().split()): r["sku"] for r in catalog}
    items = read_details(details_path, name_to_sku=name_to_sku)
    known = {r["sku"] for r in catalog}
    # Every item SKU must belong to the catalog (no inverted columns / garbage).
    assert all(it["sku"] in known for it in items)
    assert not any(it["sku"].startswith("PED-") for it in items)


def test_movements_read(movements_path):
    rows = read_movements(movements_path)
    assert len(rows) >= 150
    assert all(SKU_RE.fullmatch(r["sku"]) for r in rows)
    assert all(r["type"] in {"IN", "OUT", "ADJUSTMENT"} for r in rows)
    assert all(r["quantity"] > 0 for r in rows)
