"""Reader for the warehouse-movements workbook.

The workbook (``05_movimientos_bodega_2026.xlsx``) has one sheet per day named
``DD-MM`` (e.g. ``01-01`` = day 1 of January, ``08-06`` = day 8 of June). Each
sheet carries a header row (``SKU, DESCRIPCION, ENTRADA, SALIDA, MOTIVO,
DOCUMENTO``) plus filler rows (SALDO INICIAL / TOTAL DIA) that must be
discarded. Sheets named ``Plantilla`` and ``RESUMEN MENSUAL`` are ignored.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ..utils.normalize import looks_like_sku, normalize_sku
from ..utils.parsing import parse_int

_MOVEMENT_TYPES = None  # kept for documentation only

# Sheet-name pattern like "01-01".
_DAY_SHEET_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")

# Sheets that are structural and must never be loaded.
_IGNORE_SHEETS = {"PLANTILLA", "RESUMEN MENSUAL"}

# Movement type inferred from the reason/motivo column.
def _movement_type(motivo: object, entrada: Optional[int], salida: Optional[int]):
    if motivo is None:
        return "ADJUSTMENT"
    m = str(motivo).strip().upper()
    if "COMPRA" in m or "INGRESO" in m or "DEVOLUCI" in m.upper() or "DEVOLUCION" in m:
        return "IN" if salida is None else "IN"
    if "VENTA" in m or "DESPACHO" in m or "PEDIDO" in m or "MERMA" in m:
        return "OUT"
    if "AJUSTE" in m:
        return "ADJUSTMENT"
    # Fall back to column direction.
    if entrada is not None and entrada > 0 and (salida is None or salida == 0):
        return "IN"
    if salida is not None and salida > 0:
        return "OUT"
    return "ADJUSTMENT"


def _find_header(df: pd.DataFrame) -> int:
    """Locate the SKU/ENTRADA header row."""
    for i in range(min(10, len(df))):
        values = {str(v).strip().upper() for v in df.iloc[i].tolist() if pd.notna(v)}
        if "SKU" in values and "ENTRADA" in values and "SALIDA" in values:
            return i
    return -1


def _skip_filler(motivo: object, sku: str) -> bool:
    """Return True for rows that are not real movements."""
    if not sku:
        return True
    if isinstance(motivo, str):
        upper = motivo.strip().upper()
        if any(tag in upper for tag in ("SALDO INICIAL", "TOTAL DIA", "TOTAL")):
            return True
    return False


def _read_one_sheet(
    df: pd.DataFrame, sheet: str, month: int, day: int, movements: List[Dict]
):
    hrow = _find_header(df)
    if hrow < 0:
        return
    # Columns: SKU(0) DESCRIPCION(1) ENTRADA(2) SALIDA(3) MOTIVO(4) DOCUMENTO(5)
    for i in range(hrow + 1, len(df)):
        raw = df.iloc[i]
        if len(raw) < 6:
            continue
        sku = normalize_sku(raw[0])
        if not sku or not looks_like_sku(sku):
            continue
        motivo = raw[4]
        if _skip_filler(motivo, sku):
            continue

        entrada = parse_int(raw[2])
        salida = parse_int(raw[3])
        if (entrada is None or entrada <= 0) and (salida is None or salida <= 0):
            continue  # neither an entry nor a sale

        mtype = _movement_type(motivo, entrada, salida)
        quantity = entrada if mtype == "IN" else salida
        if quantity is None or quantity <= 0:
            quantity = (entrada or 0) + (salida or 0)
        document = str(raw[5]).strip() if pd.notna(raw[5]) else None
        reason = str(motivo).strip() if pd.notna(motivo) else None

        movement_date = None
        try:
            movement_date = date(2026, month, day)
        except ValueError:
            movement_date = None

        # Unique external key keeps the pipeline idempotent.
        external_key = f"{sheet}:{sku}:{mtype}:{document or 'NA'}:{reason or 'NA'}"

        movements.append(
            {
                "sku": sku,
                "type": mtype,
                "quantity": quantity,
                "reason": reason,
                "document": document,
                "movement_date": movement_date,
                "source": "ETL",
                "external_key": external_key,
            }
        )


def read_movements(path: str) -> List[Dict]:
    """Read the movements workbook into a list of movement dicts."""
    xl = pd.ExcelFile(path)
    movements: List[Dict] = []

    for sheet in xl.sheet_names:
        if sheet.strip().upper() in {s.upper() for s in _IGNORE_SHEETS}:
            continue
        m = _DAY_SHEET_RE.match(sheet.strip())
        if not m:
            continue
        day = int(m.group(1))
        month = int(m.group(2))
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        _read_one_sheet(df, sheet, month, day, movements)

    return movements
