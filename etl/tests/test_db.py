"""Regression tests for synchronization SQL."""

from src import db


class _Result:
    rowcount = 1


class _Connection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        return _Result()


def test_product_sync_preserves_operational_stock_delta():
    conn = _Connection()

    written = db.upsert_products(
        conn,
        [{"sku": "FER-0001", "name": "Martillo", "stock": 22, "price": 1000}],
    )

    sql = conn.statements[0][0]
    assert written == 1
    assert "catalog_stock" in sql
    assert "products.stock + EXCLUDED.catalog_stock" in sql


def test_existing_order_item_is_updated(monkeypatch):
    conn = _Connection()
    monkeypatch.setattr(
        db,
        "_lookups",
        lambda _conn: {
            "orders": {"PED-1001": "order-id"},
            "products": {"FER-0001": "product-id"},
        },
    )

    written = db.link_order_items(
        conn,
        [
            {
                "order_number": "PED-1001",
                "sku": "FER-0001",
                "quantity": 27,
                "unit_price": 1000,
            }
        ],
    )

    sql = conn.statements[0][0]
    assert written == 1
    assert "DO UPDATE SET" in sql
    assert "quantity = EXCLUDED.quantity" in sql
    assert "unit_price = EXCLUDED.unit_price" in sql


def test_existing_movement_is_updated(monkeypatch):
    conn = _Connection()
    monkeypatch.setattr(
        db,
        "_lookups",
        lambda _conn: {"orders": {}, "products": {"FER-0001": "product-id"}},
    )

    written = db.upsert_movements(
        conn,
        [
            {
                "sku": "FER-0001",
                "type": "IN",
                "quantity": 9,
                "movement_date": "2026-01-01",
                "external_key": "movement-1",
            }
        ],
    )

    sql = conn.statements[0][0]
    assert written == 1
    assert "DO UPDATE SET" in sql
    assert "quantity = EXCLUDED.quantity" in sql
    assert "movement_date = EXCLUDED.movement_date" in sql
