"""pytest configuration.

Ensures the ``etl/`` root is importable so the ``src`` package and its
relative-import modules can be imported regardless of the invocation directory,
and exposes shared fixtures pointing at the example workbooks.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_DATA = os.path.join(_ROOT, "..", "data", "examples")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def data_dir() -> str:
    return os.path.abspath(_DATA)


@pytest.fixture(scope="session")
def catalog_path(data_dir: str) -> str:
    return os.path.join(data_dir, "01_catalogo_productos_2026.xlsx")


@pytest.fixture(scope="session")
def orders_path(data_dir: str) -> str:
    return os.path.join(data_dir, "02_pedidos_externos_2026_ENE-JUN.xlsx")


@pytest.fixture(scope="session")
def details_path(data_dir: str) -> str:
    return os.path.join(data_dir, "03_detalle_pedidos_consolidado.xlsx")


@pytest.fixture(scope="session")
def movements_path(data_dir: str) -> str:
    return os.path.join(data_dir, "05_movimientos_bodega_2026.xlsx")
