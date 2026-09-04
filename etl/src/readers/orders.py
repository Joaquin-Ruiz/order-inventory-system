"""Reader for the external orders workbook (order headers).

The workbook (``02_pedidos_externos_2026_ENE-JUN.xlsx``) has a sheet per
month. Every month sheet carries a header row whose position and column order
may differ, so the header is located dynamically.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

# Sheets that must be ignored (resumen table / empty).
_IGNORE_SHEETS = {"RESUMEN", "Hoja1"}

# Recognised header labels -> canonical key.
_HEADER_ALIASES = {
    "PEDIDO": "order_number",
    "N° PEDIDO": "order_number",
    "Nº PEDIDO": "order_number",
    "N PEDIDO": "order_number",
    "NRO PEDIDO": "order_number",
    "N° PEDIDO (TEXTO)": "order_number",
    "Nº PEDIDO (TEXTO)": "order_number",
    "FECHA": "date",
    "F. EMISION": "date",
    "CLIENTE": "customer",
    "RAZON SOCIAL": "customer",
    "ESTADO": "status",
    "SITUACION": "status",
    "VENDEDOR": "vendor",
    "EJECUTIVO": "vendor",
    "CANAL": "channel",
    "DCTO %": "discount",
    "OBS": "obs",
}


def _find_header(df: pd.DataFrame) -> int:
    """Return row index of the header, or -1."""
    for i in range(min(10, len(df))):
        values = {str(v).strip().upper() for v in df.iloc[i].tolist() if pd.notna(v)}
        has_pedido = any("PEDIDO" in v for v in values)
        has_date = any(("FECHA" in v or "EMISION" in v) for v in values)
        has_customer = any(("CLIENTE" in v or "RAZON" in v) for v in values)
        if has_pedido and (has_date or has_customer):
            return i
    return -1


def _map_columns(df: pd.DataFrame, hrow: int) -> Dict[str, int]:
    """Build {canonical_key: column_index} from the header row."""
    mapping: Dict[str, int] = {}
    headers = [str(v).strip() for v in df.iloc[hrow].tolist()]
    for idx, raw in enumerate(headers):
        key = raw.upper().strip()
        for alias, canonical in _HEADER_ALIASES.items():
            if key == alias.upper().strip():
                mapping[canonical] = idx
                break
    return mapping


def _normalize_order_number(value: object) -> str:
    """Turn a raw order number (possibly with spaces or leading zeros) into
    ``PED-<digits>`` with the digits deduplicated (PED-001193 -> PED-1193)."""
    if value is None:
        return ""
    text = str(value).strip()
    # Excel serials were already turned into 5-digit dates by read_excel in
    # some columns, but here the cell is usually a string or number.
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    # Trim leading zeros silently converting 001193 -> 1193.
    number = str(int(digits))
    return f"PED-{number}"


def read_order_headers(path: str) -> List[Dict]:
    """Read all month sheets into a list of raw order-header dicts."""
    xl = pd.ExcelFile(path)
    rows: List[Dict] = []

    for sheet in xl.sheet_names:
        if sheet in _IGNORE_SHEETS:
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        hrow = _find_header(df)
        if hrow < 0:
            continue
        cols = _map_columns(df, hrow)
        if "order_number" not in cols:
            continue

        for i in range(hrow + 1, len(df)):
            raw = df.iloc[i]
            order_number = _normalize_order_number(
                raw[cols["order_number"]] if cols.get("order_number") is not None and cols["order_number"] < len(raw) else None
            )
            if not order_number:
                continue

            def cell(key: str):
                idx = cols.get(key)
                if idx is None or idx >= len(raw):
                    return None
                return raw[idx]

            rows.append(
                {
                    "order_number": order_number,
                    "date": cell("date"),
                    "customer": cell("customer"),
                    "status": cell("status"),
                    "vendor": cell("vendor"),
                    "channel": cell("channel"),
                    "discount": cell("discount"),
                    "obs": cell("obs"),
                }
            )

    # Last occurrence of a given order number wins (dedupe in later load).
    deduped: Dict[str, Dict] = {}
    for r in rows:
        deduped[r["order_number"]] = r
    return list(deduped.values())
