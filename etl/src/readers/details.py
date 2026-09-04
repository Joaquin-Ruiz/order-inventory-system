"""Reader for the order-detail workbook (order items).

The workbook (``03_detalle_pedidos_consolidado.xlsx``) holds several
sequential blocks (“CARGAs”), each introduced by a ``>>> CARGA NN <<<`` banner
and its own header row whose **column labels** dictate the layout:

  * CARGA 01 — ``PEDIDO, SKU, CANT, P.UNIT``  (order in col 0).
  * CARGA 02 — ``SKU, PEDIDO, CANTIDAD, PRECIO UNITARIO`` (reversed order).
  * CARGA 03 — ``PEDIDO, PRODUCTO, UNIDADES, VALOR UNIT`` (no SKU, only a
    description that must be resolved against the catalog).
  * CARGA 04 — ``PEDIDO, SKU, DESCRIPCION, CANT., PRECIO, …`` (price in col 4).
  * CARGA 05 — ``PEDIDO, SKU, [flag], CANT, P.UNIT`` (quantity in col 3, a
    status flag in col 2, price in col 4).

A ``DETALLE ANEXO`` sheet carries a late “CARGA TARDIA” block with the same
``NRO PEDIDO, CODIGO, CANTIDAD, VALOR UNITARIO`` layout.

Column roles are resolved from the header labels using whole-word matching so
that data rows (e.g. ``PED-1192``, ``transformador 12v``) are never confused
with headers. Each block ends at the next banner or at the sheet end.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import pandas as pd

from ..utils.normalize import looks_like_sku, normalize_sku
from ..utils.parsing import parse_int, parse_number

# Column-label aliases -> role. Aliases are matched as whole words.
_HEADER_ROLES = [
    ("order", ("PEDIDO", "NRO PEDIDO", "NO PEDIDO", "NUMERO")),
    ("sku", ("SKU", "CODIGO")),
    ("desc", ("PRODUCTO", "DESCRIPCION", "NOMBRE")),
    ("qty", ("CANT", "CANTIDAD", "UNIDADES", "PZAS")),
    ("price", ("P.UNIT", "PRECIO UNITARIO", "VALOR UNITARIO", "VALOR UNIT",
               "PRECIO", "PRECIO UNIT")),
]


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return " ".join(str(value).strip().split())


def _norm_word(word: str) -> str:
    """Normalise a single token for matching (strip punctuation/currency)."""
    return re.sub(r"[^A-Z0-9]+", "", word.upper())


def _cell_tokens(value: object) -> List[str]:
    """Tokenise a header cell into normalised words (e.g. ``P.UNIT`` -> PUNIT)."""
    return [_norm_word(w) for w in _text(value).split() if _norm_word(w)]


def _build_colmap(header: pd.Series) -> Dict[str, int]:
    """Map a role to the column whose header labels match it.

    A header cell matches a role when *any* of its normalised tokens equals one
    of the role's normalised aliases. ``P.UNIT`` (one token ``PUNIT``) matches
    the ``P.UNIT`` alias; ``VALOR UNIT`` (tokens ``VALOR`` + ``UNIT``) matches
    neither half alone, so a full-cell match is also tried for multi-word
    aliases such as ``VALOR UNIT`` and ``PRECIO UNITARIO``.
    """
    colmap: Dict[str, int] = {}
    for idx, value in enumerate(header):
        tokens = _cell_tokens(value)
        if not tokens:
            continue
        cell_full = "".join(tokens)
        for role, aliases in _HEADER_ROLES:
            if role in colmap:
                continue
            for alias in aliases:
                akey = _norm_word(alias)
                if akey in tokens or akey == cell_full:
                    colmap[role] = idx
                    break
    return colmap


def _is_banner(cell: object) -> bool:
    return _text(cell).upper().startswith(">>>") and "CARGA" in _text(cell).upper()


def _is_empty_row(row: pd.Series) -> bool:
    return all(pd.isna(row[c]) for c in range(len(row)))


def _has_core_cols(colmap: Dict[str, int]) -> bool:
    return colmap.get("qty") is not None and colmap.get("price") is not None


def _order_number(value: object) -> Optional[str]:
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not digits:
        return None
    return f"PED-{int(digits)}"


def _sku_from_cell(value: object, name_to_sku: Optional[Dict[str, str]]) -> Optional[str]:
    sku = normalize_sku(value)
    if not sku or not looks_like_sku(sku):
        return None
    return sku


def _sku_from_desc(value: object, name_to_sku: Optional[Dict[str, str]]) -> Optional[str]:
    if not name_to_sku:
        return None
    key = " ".join(str(value).lower().split())
    return name_to_sku.get(key)


def _parse_block(
    df: pd.DataFrame,
    header_row: int,
    colmap: Dict[str, int],
    items: List[Dict],
    name_to_sku: Optional[Dict[str, str]],
):
    order_col = colmap.get("order")
    sku_col = colmap.get("sku")
    desc_col = colmap.get("desc")
    qty_col = colmap["qty"]
    price_col = colmap["price"]
    has_desc = sku_col is None and desc_col is not None

    for r in range(header_row + 1, len(df)):
        raw = df.iloc[r]
        if _is_empty_row(raw):
            break
        if _is_banner(raw[0]):
            break
        if order_col is None:
            continue
        order_number = _order_number(raw[order_col])
        if not order_number:
            continue

        if has_desc:
            sku = _sku_from_desc(raw[desc_col], name_to_sku)
        else:
            sku = _sku_from_cell(raw[sku_col], name_to_sku)
        if not sku:
            continue

        quantity = parse_int(raw[qty_col])
        unit_price = parse_number(raw[price_col])
        if quantity is None or unit_price is None or quantity <= 0 or unit_price <= 0:
            continue

        items.append(
            {
                "order_number": order_number,
                "sku": sku,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        )


def _find_header(df: pd.DataFrame, from_row: int) -> Optional[int]:
    """Locate the header row at/after ``from_row`` (skips banner/note rows)."""
    for j in range(from_row, min(from_row + 8, len(df))):
        if _is_empty_row(df.iloc[j]):
            continue
        if _is_banner(df.iloc[j][0]):
            continue
        colmap = _build_colmap(df.iloc[j])
        if _has_core_cols(colmap) and colmap.get("order") is not None:
            return j
    return None


def _parse_sheet(df: pd.DataFrame, items: List[Dict], name_to_sku: Optional[Dict[str, str]]):
    """Scan the sheet for block headers (after banners, or bare headers such as
    the ANEXO) and load every block found into ``items``."""
    idx = 0
    while idx < len(df):
        header_row = _find_header(df, idx)
        if header_row is None:
            break
        colmap = _build_colmap(df.iloc[header_row])

        # Parse rows from just after the header until the next banner/header
        # delimiter or the end of the sheet.
        _parse_block(df, header_row, colmap, items, name_to_sku)

        # Advance past this block to the next banner/header.
        idx = header_row + 1
        while idx < len(df) and not _is_banner(df.iloc[idx][0]):
            idx += 1


def read_details(path: str, name_to_sku: Optional[Dict[str, str]] = None) -> List[Dict]:
    """Parse the order-detail workbook into a list of item dicts.

    ``name_to_sku`` maps a normalised description key to a canonical SKU and is
    needed for description-only blocks (CARGA 03). Both the ``DETALLE`` sheet
    and the ``DETALLE ANEXO`` (late “CARGA TARDIA”) sheet are processed.
    """
    items: List[Dict] = []
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        if sheet.upper() not in {"DETALLE", "DETALLE ANEXO"}:
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        _parse_sheet(df, items, name_to_sku)
    return items
