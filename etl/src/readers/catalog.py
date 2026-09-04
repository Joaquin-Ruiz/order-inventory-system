"""Reader for the product catalog workbook.

The catalog workbook (``01_catalogo_productos_2026.xlsx``) has one sheet per
family, each with its own header row, column order and value formats, plus a
“CORRECCIONES” sheet that overrides published price/stock values.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from ..utils.normalize import looks_like_sku, normalize_sku
from ..utils.parsing import parse_number, parse_quantity

# Sheets that must never be treated as product data.
_IGNORE_SHEETS = {"LINEA NUEVA 2027", "plantilla"}
# The corrections sheet published by the buying area (marzo).
_CORRECTIONS_SHEET = "CORRECCIONES MARZO"


def _is_active(raw_state: object) -> bool:
    """Map the very inconsistent state column to a boolean.

    ``SI``/``VIGENTE``/``ACTIVO``/``1``/``X``/``S``/``A``-style tokens mean
    active in these files; explicit ``DESC``/``BAJA``/``descontinuado`` are
    inactive; blanks default to active (catalog presence implies active).
    """
    if raw_state is None or (isinstance(raw_state, float) and pd.isna(raw_state)):
        return True  # blank -> assume active
    key = str(raw_state).strip().upper()
    if not key:
        return True
    if key in {"DESC", "BAJA", "DESCONTINUADO", "D", "0", "N", "NO", "2"}:
        return False
    return True


def _coin_price(row: List, idx: int) -> Optional[float]:
    """Return the parsed price in CLP at column ``idx`` (0 = not present)."""
    if idx < 0 or idx >= len(row):
        return None
    return parse_number(row[idx])


class _SheetSpec:
    """Describes how to locate the header + columns for one sheet kind."""

    __slots__ = ("header_scan_max", "sku", "name", "stock", "price", "state")

    def __init__(self, sku, name, stock, price, state, header_scan_max=15):
        self.sku = sku
        self.name = name
        self.stock = stock
        self.price = price
        self.state = state
        self.header_scan_max = header_scan_max

    def find_header(self, df: pd.DataFrame) -> int:
        """Return the row index where the SKU column is the header.

        The SKU column position is fixed per sheet (``self.sku``), so we scan
        for a cell in that column whose text looks like a column header.
        """
        for i in range(min(self.header_scan_max, len(df))):
            if i >= len(df):
                break
            cell = df.iloc[i][self.sku] if self.sku < len(df.iloc[i]) else None
            if cell is None:
                continue
            text = str(cell).strip().upper()
            # Ignore quotes/whitespace common in these files ("'SKU'").
            text = text.replace("'", "").replace('"', "").strip()
            if text in {"SKU", "CODIGO", "CO\u00d3DIGO"}:
                return i
        return -1


# Family sheet specifications (name, sku_col, name_col, stock_col, price_col, state_col).
_SHEETS = {
    "FERRETERIA": _SheetSpec(
        sku=0, name=1, stock=2, price=3, state=5, header_scan_max=10
    ),
    "Linea Electrica": _SheetSpec(
        sku=0, name=2, stock=3, price=1, state=7, header_scan_max=10
    ),
    "HOGAR ": _SheetSpec(
        sku=0, name=1, stock=2, price=3, state=4, header_scan_max=10
    ),
    "SEGURIDAD": _SheetSpec(
        sku=0, name=1, stock=2, price=3, state=4, header_scan_max=10
    ),
}


def _scan_family_rows(df: pd.DataFrame, spec: _SheetSpec, hrow: int, rows: List[Dict]):
    """Extract product rows from a single-column-order family sheet."""
    for i in range(hrow + 1, len(df)):
        raw = df.iloc[i]
        if len(raw) <= max(spec.sku, spec.name, spec.stock, spec.price, spec.state):
            continue
        raw_sku = raw[spec.sku]
        sku = normalize_sku(raw_sku)
        # Skip section banners, totals and empty SKU cells.
        if not sku or not looks_like_sku(sku):
            continue
        if isinstance(raw_sku, str) and any(
            marker in raw_sku.upper()
            for marker in ("---", "TOTAL", "SUBTOTAL", "LIQUIDACION")
        ):
            continue

        name = str(raw[spec.name]).strip() if pd.notna(raw[spec.name]) else ""
        if not name:
            continue

        stock = parse_quantity(raw[spec.stock])
        price = parse_number(raw[spec.price])
        state_raw = raw[spec.state] if spec.state < len(raw) else None

        rows.append(
            {
                "sku": sku,
                "name": name,
                "stock": stock if stock is not None else 0,
                "price": price if price is not None else 0,
                "active": _is_active(state_raw),
            }
        )


def _read_seguridad_two_blocks(df: pd.DataFrame, rows: List[Dict]):
    """SEGURIDAD has a first block (SKU,desc,stock,price,state) then a
    “CARGA COMPLEMENTARIA” block with columns in a different order.
    """
    spec = _SHEETS["SEGURIDAD"]
    hrow = spec.find_header(df)
    if hrow < 0:
        return
    _scan_family_rows(df, spec, hrow, rows)

    # Second block starts at the '>>> CARGA COMPLEMENTARIA' banner.
    start = None
    for i in range(hrow + 1, len(df)):
        cell = df.iloc[i][0] if len(df.iloc[i]) > 0 else None
        if isinstance(cell, str) and "CARGA" in cell.upper():
            start = i
            break
    if start is None:
        return

    # Its header row is one below the banner; order is DESC, PRECIO, SKU, ESTADO, STOCK.
    for i in range(start + 1, len(df)):
        raw = df.iloc[i]
        if len(raw) < 5:
            continue
        sku = normalize_sku(raw[2])
        if not sku or not looks_like_sku(sku):
            continue
        name = str(raw[0]).strip() if pd.notna(raw[0]) else ""
        if not name:
            continue
        price = parse_number(raw[1])
        state_raw = raw[3]
        stock = parse_quantity(raw[4])
        rows.append(
            {
                "sku": sku,
                "name": name,
                "stock": stock if stock is not None else 0,
                "price": price if price is not None else 0,
                "active": _is_active(state_raw),
            }
        )


def _read_corrections(df: pd.DataFrame) -> Dict[str, Dict[str, object]]:
    """Parse the CORRECCIONES sheet into {sku: {price, stock, date}}.

    In case of repeated SKUs the row with the most recent update date wins.
    """
    result: Dict[str, Dict[str, object]] = {}
    hrow = None
    for i in range(min(8, len(df))):
        values = [str(v).strip().upper() for v in df.iloc[i].tolist()]
        if "SKU" in values and "PRECIO VENTA" in values:
            hrow = i
            break
    if hrow is None:
        return result

    for i in range(hrow + 1, len(df)):
        raw = df.iloc[i]
        if len(raw) < 5:
            continue
        sku = normalize_sku(raw[0])
        if not sku or not looks_like_sku(sku):
            continue
        price = parse_number(raw[2])
        stock = parse_quantity(raw[3])
        date_raw = raw[4]
        entry = result.setdefault(sku, {"price": None, "stock": None, "date": None})
        entry["price"] = price if entry["price"] is None else entry["price"]
        entry["stock"] = stock if entry["stock"] is None else entry["stock"]
        # Keep the latest date marker (best-effort ordering).
        if date_raw is not None:
            entry["date"] = str(date_raw)
    return result


def read_catalog(path: str) -> List[Dict]:
    """Read the catalog workbook into a list of normalised product dicts."""
    xl = pd.ExcelFile(path)
    rows: List[Dict] = []

    # 1. Base rows from each family sheet.
    for sheet in xl.sheet_names:
        if sheet in _IGNORE_SHEETS or sheet.strip() == "PLANTILLA - NO USAR":
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        if sheet == "SEGURIDAD":
            _read_seguridad_two_blocks(df, rows)
        elif sheet in _SHEETS:
            spec = _SHEETS[sheet]
            hrow = spec.find_header(df)
            if hrow >= 0:
                _scan_family_rows(df, spec, hrow, rows)

    # 2. Apply the corrections sheet (price/stock overrides).
    if _CORRECTIONS_SHEET in xl.sheet_names:
        corrections = _read_corrections(
            pd.read_excel(path, sheet_name=_CORRECTIONS_SHEET, header=None)
        )
        for row in rows:
            corr = corrections.get(row["sku"])
            if corr:
                if corr["price"] is not None:
                    row["price"] = corr["price"]
                if corr["stock"] is not None:
                    row["stock"] = corr["stock"]

    return rows
