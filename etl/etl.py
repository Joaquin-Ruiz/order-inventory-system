#!/usr/bin/env python3
"""Order/inventory ETL pipeline.

Reads the messy Excel workbooks in ``data/examples``, normalises them (reusing
the API's SKU/date/number rules), validates data quality, and upserts the
result into the shared PostgreSQL tables used by the API.

Usage (from the ``etl/`` directory)::

    python etl.py                      # run all sources (idempotent)
    python etl.py catalog              # only the product catalog
    python etl.py --input /path/x.xlsx # a single workbook
    python etl.py --dry-run            # read/clean/validate without writing

Exit code is non-zero when the run fails; validation rejections are reported
but do not fail the pipeline unless ``--strict`` is passed.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

# Make ``src`` importable regardless of the current working directory.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import db as repo  # noqa: E402
from src.cleaners import (  # noqa: E402
    clean_movements,
    clean_order_items,
    clean_orders,
    clean_products,
)
from src.config import Settings, load_settings  # noqa: E402
from src.readers import read_catalog, read_details, read_movements, read_order_headers  # noqa: E402
from src.validators import (  # noqa: E402
    validate_movements,
    validate_order_items,
    validate_orders,
    validate_products,
)

_DEFAULT_DATA = os.path.join(_ROOT, "..", "data", "examples")

_FILENAMES = {
    "catalog": "01_catalogo_productos_2026.xlsx",
    "orders": "02_pedidos_externos_2026_ENE-JUN.xlsx",
    "details": "03_detalle_pedidos_consolidado.xlsx",
    "movements": "05_movimientos_bodega_2026.xlsx",
}
_SUPPORTED = set(_FILENAMES)
_ORDER = ("catalog", "orders", "details", "movements")


@dataclass
class JobResult:
    kind: str
    raw: int = 0
    cleaned: int = 0
    rejected: int = 0
    written: int = 0
    reasons: Dict[str, int] = field(default_factory=dict)
    path: str = ""
    skipped: bool = False

    def to_row(self) -> str:
        return (
            f"{self.kind:<10} raw={self.raw:<6} cleaned={self.cleaned:<6} "
            f"rejected={self.rejected:<6} written={self.written}"
        )


def _locate_file(folder: str, inputs: Optional[List[str]], kind: str) -> Optional[str]:
    """Return the workbook path for ``kind`` given the --input argument(s)."""
    if inputs:
        for p in inputs:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                cand = os.path.join(p, _FILENAMES[kind])
                if os.path.exists(cand):
                    return cand
            elif os.path.isfile(p):
                # Explicit workbooks may be renamed by a scheduler. Detect
                # their source from content instead of relying on basename.
                if (
                    os.path.basename(p) == _FILENAMES[kind]
                    or _infer_source_kind(p) == kind
                ):
                    return p
        return None
    cand = os.path.join(folder, _FILENAMES[kind])
    return cand if os.path.exists(cand) else None


def _read_raw(kind: str, path: str, name_to_sku: Optional[Dict[str, str]]) -> List[Dict]:
    if kind == "catalog":
        return read_catalog(path)
    if kind == "orders":
        return read_order_headers(path)
    if kind == "details":
        return read_details(path, name_to_sku=name_to_sku)
    if kind == "movements":
        return read_movements(path)
    raise ValueError(f"unknown source {kind!r}")


@lru_cache(maxsize=32)
def _infer_source_kind(path: str) -> Optional[str]:
    """Identify a renamed workbook by the reader that recognizes its content."""
    matches: List[str] = []
    for kind in _ORDER:
        try:
            if _read_raw(kind, path, None):
                matches.append(kind)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return matches[0] if len(matches) == 1 else None


def _clean(kind: str, raw: List[Dict]) -> List[Dict]:
    fn = {
        "catalog": clean_products,
        "orders": clean_orders,
        "details": clean_order_items,
        "movements": clean_movements,
    }[kind]
    return fn(raw)


def _validate(kind: str, cleaned: List[Dict]):
    fn = {
        "catalog": validate_products,
        "orders": validate_orders,
        "details": validate_order_items,
        "movements": validate_movements,
    }[kind]
    return fn(cleaned)


def _write(kind: str, conn, cleaned: List[Dict]) -> int:
    fn = {
        "catalog": repo.upsert_products,
        "orders": repo.upsert_orders,
        "details": repo.link_order_items,
        "movements": repo.upsert_movements,
    }[kind]
    return fn(conn, cleaned)


def _run_one(
    kind: str,
    path: str,
    name_to_sku: Optional[Dict[str, str]],
    conn,
    dry_run: bool,
    strict: bool,
) -> JobResult:
    job = JobResult(kind=kind, path=path)
    raw = _read_raw(kind, path, name_to_sku)
    job.raw = len(raw)
    cleaned = _clean(kind, raw)
    job.cleaned = len(cleaned)
    res = _validate(kind, cleaned)
    job.rejected = res.rejected
    job.reasons = res.reasons
    accepted = res.accepted_rows

    if dry_run or conn is None:
        job.skipped = dry_run or conn is None
        return job
    try:
        job.written = _write(kind, conn, accepted)
        conn.commit()
    except Exception as exc:  # surface DB errors clearly
        conn.rollback()
        if strict:
            raise
        print(f"  [warn] {kind} write failed: {exc}", file=sys.stderr)
        job.written = -1
    return job


def _name_to_sku(catalog_rows: List[Dict]) -> Dict[str, str]:
    return {" ".join(str(r["name"]).lower().split()): r["sku"] for r in catalog_rows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="sources to run (catalog, orders, details, movements); default: all",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        help="folder or explicit workbook path(s) instead of the default",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="read/clean/validate but do not write to the database",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail the process on any database error",
    )
    parser.add_argument(
        "--db-url",
        help="database URL (overrides ETL_DATABASE_URL / DATABASE_URL)",
    )
    args = parser.parse_args(argv)

    settings: Optional[Settings] = None
    if not args.dry_run:
        settings = (
            Settings(database_url=args.db_url)
            if args.db_url
            else load_settings()
        )

    folder = _DEFAULT_DATA
    if args.input and os.path.isdir(os.path.abspath(args.input[0])):
        folder = os.path.abspath(args.input[0])
    elif not args.input:
        folder = os.path.abspath(_DEFAULT_DATA)

    if args.sources:
        kinds = list(dict.fromkeys(args.sources))
    elif args.input and all(os.path.isfile(os.path.abspath(p)) for p in args.input):
        detected = [_infer_source_kind(os.path.abspath(p)) for p in args.input]
        if any(kind is None for kind in detected):
            print(
                "Could not identify one or more explicit input workbooks",
                file=sys.stderr,
            )
            return 2
        kinds = list(dict.fromkeys(kind for kind in detected if kind is not None))
    else:
        kinds = list(_ORDER)
    invalid = [k for k in kinds if k not in _SUPPORTED]
    if invalid:
        print(f"Unknown source(s): {', '.join(invalid)}", file=sys.stderr)
        return 2

    print(f"data location : {folder}")
    print(f"dry-run       : {args.dry_run}")
    print(f"sources       : {', '.join(kinds)}")

    conn = None
    if not args.dry_run:
        assert settings is not None
        conn = repo.create_connection(settings)
        print("database      : connected")

    results: List[JobResult] = []
    missing_sources: List[str] = []
    name_to_sku: Optional[Dict[str, str]] = None
    try:
        # Load the catalog whenever it is needed:
        #  * as a source itself, and/or
        #  * as the name->sku index for description-only order details.
        needs_catalog = "catalog" in kinds or "details" in kinds
        if needs_catalog:
            cat_path = _locate_file(folder, args.input, "catalog")
            if cat_path:
                if "catalog" in kinds:
                    job = _run_one("catalog", cat_path, None, conn, args.dry_run, args.strict)
                    results.append(job)
                # Build the in-memory index from the same file (read again only
                # if we did not already have the cleaned rows handy).
                if name_to_sku is None:
                    catalog_rows = read_catalog(cat_path)
                    name_to_sku = _name_to_sku(catalog_rows)
            else:
                if "catalog" in kinds:
                    print("  [skip] catalog workbook not found")
                    missing_sources.append("catalog")

        for kind in ("orders", "details", "movements"):
            if kind not in kinds:
                continue
            path = _locate_file(folder, args.input, kind)
            if not path:
                print(f"  [skip] {kind} workbook not found")
                missing_sources.append(kind)
                continue
            sku_index = name_to_sku if kind == "details" else None
            job = _run_one(kind, path, sku_index, conn, args.dry_run, args.strict)
            results.append(job)
    finally:
        if conn is not None:
            conn.close()

    print("\n--- data-quality report ---")
    for r in results:
        line = " " + r.to_row()
        if r.skipped:
            line += "  (dry-run)"
        print(line)
        for reason, count in r.reasons.items():
            print(f"     rejected-{reason}: {count}")
    print("---------------------------")
    if missing_sources:
        print(
            f"Missing requested source(s): {', '.join(missing_sources)}",
            file=sys.stderr,
        )
        return 1
    if any(result.written < 0 for result in results):
        return 1
    if not results:
        print("No source was processed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
