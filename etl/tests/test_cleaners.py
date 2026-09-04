"""Tests for cleaners and validators."""

from datetime import date

from src.cleaners import (
    clean_movements,
    clean_order_items,
    clean_orders,
    clean_products,
)
from src.validators import (
    validate_movements,
    validate_order_items,
    validate_orders,
    validate_products,
)


# --- products ------------------------------------------------------------
def test_clean_products_strips_hogar_iva():
    rows = [
        {"sku": "HOG-0001", "name": "Test", "stock": 5, "price": 1190.0,
         "active": True, "family": "HOGAR"},
    ]
    out = clean_products(rows)
    assert out[0]["price"] == round(1190.0 / 1.19, 2)  # 1000.0


def test_clean_products_net_untouched():
    rows = [
        {"sku": "FER-0001", "name": "M", "stock": 3, "price": 1000.0,
         "active": True, "family": "FERRETERIA"},
    ]
    out = clean_products(rows)
    assert out[0]["price"] == 1000.0


def test_clean_products_dedupe_last_wins():
    rows = [
        {"sku": "FER-0001", "name": "A", "stock": 1, "price": 10.0,
         "active": True, "family": "F"},
        {"sku": "FER-0001", "name": "B", "stock": 2, "price": 20.0,
         "active": True, "family": "F"},
    ]
    out = clean_products(rows)
    assert len(out) == 1
    assert out[0]["name"] == "B"
    assert out[0]["price"] == 20.0


# --- orders --------------------------------------------------------------
def test_clean_orders_dedupes_and_normalises():
    rows = [
        {"order_number": "PED-1001", "date": "14-abr-26",
         "customer": "X", "status": "Despachado"},
        {"order_number": "PED-1001", "date": "15-abr-26",
         "customer": "X", "status": "OK"},
    ]
    out = clean_orders(rows)
    assert len(out) == 1
    assert out[0]["date"] == date(2026, 4, 15)
    assert out[0]["status"] == "COMPLETED"
    assert out[0]["source"] == "ETL"


def test_validate_orders_reports_bad_date():
    rows = [
        {"order_number": "PED-1", "date": date(2026, 1, 1),
         "status": "PENDING", "customer": "", "source": "ETL"},
        {"order_number": "PED-2", "date": None,
         "status": "PENDING", "customer": "", "source": "ETL"},
    ]
    res = validate_orders(rows)
    assert res.accepted == 1
    assert res.rejected == 1
    assert res.reasons.get("invalid_date") == 1


# --- order items ---------------------------------------------------------
def test_clean_order_items_aggregates_quantity():
    items = [
        {"order_number": "PED-1001", "sku": "FER-0001", "quantity": 2, "unit_price": 100.0},
        {"order_number": "PED-1001", "sku": "FER-0001", "quantity": 3, "unit_price": 100.0},
        {"order_number": "PED-1001", "sku": "FER-0002", "quantity": 1, "unit_price": 50.0},
    ]
    out = clean_order_items(items)
    aggregated = {x["order_number"] + x["sku"]: x for x in out}
    assert len(out) == 2
    assert aggregated["PED-1001FER-0001"]["quantity"] == 5


def test_validate_order_items():
    rows = [
        {"order_number": "PED-1", "sku": "FER-0001", "quantity": 2, "unit_price": 10.0},
        {"order_number": "PED-2", "sku": "BAD", "quantity": 2, "unit_price": 10.0},
    ]
    res = validate_order_items(rows)
    assert res.accepted == 1
    assert res.rejected == 1
    assert res.reasons.get("invalid_sku") == 1


# --- movements -----------------------------------------------------------
def test_clean_movements_keeps_valid():
    rows = [
        {"sku": "FER-0001", "type": "OUT", "quantity": 4,
         "reason": "venta", "document": "PED-1018",
         "movement_date": date(2026, 1, 2), "source": "ETL",
         "external_key": "01-01:FER-0001:OUT:PED-1018:VENTA"},
        {"sku": "FER-0001", "type": "OUT", "quantity": 0,
         "reason": None, "document": None,
         "movement_date": date(2026, 1, 2), "source": "ETL",
         "external_key": "x"},
    ]
    out = clean_movements(rows)
    assert len(out) == 1


def test_validate_movements_type():
    rows = [
        {"sku": "FER-0001", "type": "OUT", "quantity": 1,
         "movement_date": date(2026, 1, 1), "external_key": "k1"},
        {"sku": "FER-0001", "type": "RANDOM", "quantity": 1,
         "movement_date": date(2026, 1, 1), "external_key": "k2"},
    ]
    res = validate_movements(rows)
    assert res.rejected == 1
    assert res.reasons.get("invalid_type") == 1
