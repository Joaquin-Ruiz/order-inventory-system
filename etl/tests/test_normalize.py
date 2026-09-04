"""Tests for SKU normalisation (shared rule with the API)."""

from src.utils.normalize import looks_like_sku, normalize_sku


def test_pads_to_four_digits():
    assert normalize_sku("FER-10") == "FER-0010"
    assert normalize_sku("FER10") == "FER-0010"
    assert normalize_sku("HOG-0004") == "HOG-0004"


def test_handles_messy_input():
    assert normalize_sku("  SEG_0010 ") == "SEG-0010"
    assert normalize_sku("ele-0011") == "ELE-0011"
    assert normalize_sku("HOG-5") == "HOG-0005"


def test_blank_and_none():
    assert normalize_sku(None) == ""
    assert normalize_sku("") == ""


def test_non_sku_passthrough():
    # Garbage / descriptions should not silently become valid SKUs.
    assert normalize_sku("SIN CODIGO") != ""
    assert not looks_like_sku("SIN CODIGO")


def test_looks_like_sku_only_canonical():
    assert looks_like_sku("FER-0010")
    assert looks_like_sku("SEG-0009")
    assert not looks_like_sku("SIN CODIGO")
    assert not looks_like_sku("transformador")
    assert not looks_like_sku("ZZZ")
    assert not looks_like_sku("")
