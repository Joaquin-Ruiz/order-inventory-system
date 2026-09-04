"""Tests for the messy-data parsing helpers."""

from datetime import date

from src.utils.parsing import (
    parse_date,
    parse_int,
    parse_number,
    parse_order_status,
    parse_quantity,
)


# --- numbers -------------------------------------------------------------
def test_parse_number_formats():
    assert parse_number(12430) == 12430.0
    assert parse_number("5.260") == 5260.0
    assert parse_number("1.760,00") == 1760.0
    assert parse_number("$ 38.640") == 38640.0
    assert parse_number("$18.020.-") == 18020.0


def test_parse_number_comma_decimal():
    assert parse_number("1,58") == 1.58
    assert parse_number("3,09") == 3.09


def test_parse_quantity_with_units():
    assert parse_quantity("2 un") == 2
    assert parse_quantity("24 un") == 24
    assert parse_quantity("5 un.") == 5
    assert parse_quantity("10,0") == 10
    assert parse_quantity("-") is None
    assert parse_quantity("s/i") is None


def test_parse_int_rounds():
    assert parse_int("6") == 6
    assert parse_int(60000) == 60000


# --- dates ---------------------------------------------------------------
def test_parse_iso_date():
    assert parse_date("2026-04-20 00:00:00") == date(2026, 4, 20)
    assert parse_date("2026-06-09") == date(2026, 6, 9)


def test_parse_invalid_iso_date_is_not_reinterpreted():
    assert parse_date("2026-13-05") is None


def test_parse_excel_serial():
    assert parse_date(46132) == date(2026, 4, 20)


def test_parse_spanish_short_year():
    assert parse_date("14-abr-26") == date(2026, 4, 14)
    assert parse_date("03-may-26") == date(2026, 5, 3)
    assert parse_date("15-jun-26") == date(2026, 6, 15)


def test_parse_spanish_de_form():
    assert parse_date("28 de abr de 26") == date(2026, 4, 28)
    assert parse_date("21 de may de 26") == date(2026, 5, 21)
    assert parse_date("18 de enero de 2026") == date(2026, 1, 18)


def test_parse_impossible_date_is_none():
    # 31 de abril no existe -> se descarta como dato sucio.
    assert parse_date("31-04-2026") is None


def test_parse_blank_is_none():
    assert parse_date(None) is None
    assert parse_date("") is None


# --- order status --------------------------------------------------------
def test_parse_status_mapping():
    assert parse_order_status("Despachado") == "DISPATCHED"
    assert parse_order_status("ENTREG.") == "COMPLETED"
    assert parse_order_status("PENDIENTE") == "PENDING"
    assert parse_order_status("ANUL") == "CANCELLED"
    assert parse_order_status("40") == "PROCESSING"
    assert parse_order_status("desconocido") is None
