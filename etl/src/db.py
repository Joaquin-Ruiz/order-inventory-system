"""Database access layer using SQLAlchemy Core.

The repository layer writes directly to PostgreSQL with idempotent statements
so re-running the pipeline never duplicates data. Plain text ``INSERT ... ON
CONFLICT DO UPDATE`` (upsert) is used on purpose: the requirement asks for a
*sync* into shared tables, and upserts are the safest way to stay idempotent
without a full ORM migration story.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from .config import Settings


def create_connection(settings: Settings) -> Connection:
    """Open a connection to the database using the configured URL."""
    engine = create_engine(settings.database_url)
    return engine.connect()


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
def upsert_products(
    conn: Connection, rows: Iterable[Dict[str, Any]]
) -> int:
    """Insert or update products keyed by unique ``sku``. Returns rows written."""
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO products
            (id, name, sku, stock, catalog_stock, price, active, updated_at)
        VALUES
            (:id, :name, :sku, :stock, :stock, :price, :active, NOW())
        ON CONFLICT (sku) DO UPDATE SET
            name = EXCLUDED.name,
            -- Apply only the change between catalog snapshots. This keeps
            -- API sales made after the previous import instead of resetting
            -- operational stock to the workbook value on every ETL run.
            stock = GREATEST(
                0,
                products.stock + EXCLUDED.catalog_stock
                    - COALESCE(products.catalog_stock, EXCLUDED.catalog_stock)
            ),
            catalog_stock = EXCLUDED.catalog_stock,
            price = EXCLUDED.price,
            active = EXCLUDED.active,
            updated_at = NOW()
        """
    )
    payload = [
        {
            "id": str(uuid.uuid4()),
            "name": r["name"],
            "sku": r["sku"],
            "stock": r.get("stock") or 0,
            "price": r.get("price") or 0,
            "active": r.get("active", True),
        }
        for r in rows
    ]
    conn.execute(stmt, payload)
    return len(payload)


# ---------------------------------------------------------------------------
# Orders + items
# ---------------------------------------------------------------------------
def upsert_orders(conn: Connection, rows: Iterable[Dict[str, Any]]) -> int:
    """Insert or update order headers keyed by unique ``order_number``."""
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO orders (id, order_number, date, status, customer, source, updated_at)
        VALUES (:id, :order_number, :date, :status, :customer, :source, NOW())
        ON CONFLICT (order_number) DO UPDATE SET
            date = EXCLUDED.date,
            status = EXCLUDED.status,
            customer = EXCLUDED.customer,
            source = EXCLUDED.source,
            updated_at = NOW()
        """
    )
    payload = [
        {
            "id": str(uuid.uuid4()),
            "order_number": r["order_number"],
            "date": r.get("date"),
            "status": r.get("status") or "PENDING",
            "customer": r.get("customer") or "",
            "source": r.get("source") or "ETL",
        }
        for r in rows
    ]
    conn.execute(stmt, payload)
    return len(payload)


def link_order_items(
    conn: Connection,
    items: Iterable[Dict[str, Any]],
) -> int:
    """Insert order items, resolving order_number/product_id from lookups.

    Each item carries ``order_number`` and ``sku``; they are resolved against
    the current DB state so the row only lands when both exist. Idempotency is
    guaranteed by the ``(order_id, product_id)`` unique key (update existing).
    """
    if not items:
        return 0

    upsert_item = text(
        """
        INSERT INTO order_items (id, order_id, product_id, quantity, unit_price)
        VALUES (:id, :order_id, :product_id, :quantity, :unit_price)
        ON CONFLICT (order_id, product_id) DO UPDATE SET
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price
        """
    )
    lookup = _lookups(conn)
    written = 0
    for it in items:
        order_id = lookup["orders"].get(it["order_number"])
        product_id = lookup["products"].get(it["sku"])
        if order_id is None or product_id is None:
            continue
        result = conn.execute(
            upsert_item,
            {
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "product_id": product_id,
                "quantity": it["quantity"],
                "unit_price": it["unit_price"],
            },
        )
        written += result.rowcount or 0
    return written


# ---------------------------------------------------------------------------
# Inventory movements
# ---------------------------------------------------------------------------
def upsert_movements(
    conn: Connection,
    rows: Iterable[Dict[str, Any]],
) -> int:
    """Insert inventory movements, keyed by unique ``external_key`` for idempotency."""
    if not rows:
        return 0

    stmt = text(
        """
        INSERT INTO inventory_movements
            (id, product_id, type, quantity, reason, document,
             movement_date, source, external_key)
        VALUES
            (:id, :product_id, :type, :quantity, :reason, :document,
             :movement_date, :source, :external_key)
        ON CONFLICT (external_key) DO UPDATE SET
            product_id = EXCLUDED.product_id,
            type = EXCLUDED.type,
            quantity = EXCLUDED.quantity,
            reason = EXCLUDED.reason,
            document = EXCLUDED.document,
            movement_date = EXCLUDED.movement_date,
            source = EXCLUDED.source
        """
    )
    lookup = _lookups(conn)
    written = 0
    for r in rows:
        product_id = lookup["products"].get(r["sku"])
        if product_id is None or not r.get("external_key"):
            continue
        result = conn.execute(
            stmt,
            {
                "id": str(uuid.uuid4()),
                "product_id": product_id,
                "type": r["type"],
                "quantity": r["quantity"],
                "reason": r.get("reason"),
                "document": r.get("document"),
                "movement_date": r["movement_date"],
                "source": r.get("source") or "ETL",
                "external_key": r["external_key"],
            },
        )
        written += result.rowcount or 0
    return written


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _lookups(conn: Connection) -> Dict[str, Dict[str, str]]:
    """Build ``{order_number: id}`` and ``{sku: id}`` maps from the DB."""
    orders = {
        row["order_number"]: row["id"]
        for row in conn.execute(
            text("SELECT id, order_number FROM orders")
        ).mappings()
    }
    products = {
        row["sku"]: row["id"]
        for row in conn.execute(
            text("SELECT id, sku FROM products")
        ).mappings()
    }
    return {"orders": orders, "products": products}
