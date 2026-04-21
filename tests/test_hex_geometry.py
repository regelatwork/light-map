import pytest
from light_map.core.geometry import PointyTopHex, FlatTopHex


def test_pointy_top_conversions():
    spacing = 100.0
    hex_geo = PointyTopHex(spacing)

    # Center hex (0,0) should be (0,0) pixels
    assert hex_geo.to_pixel(0, 0) == (0.0, 0.0)

    # Pixel back to axial
    q, r = hex_geo.from_pixel(0, 0)
    assert q == 0.0
    assert r == 0.0

    # Neighbor hex (1,0)
    # x = size * sqrt(3) * (1 + 0) = spacing
    # y = size * 1.5 * 0 = 0
    px, py = hex_geo.to_pixel(1, 0)
    assert pytest.approx(px) == spacing
    assert pytest.approx(py) == 0.0


def test_flat_top_conversions():
    spacing = 100.0
    hex_geo = FlatTopHex(spacing)

    # Center hex (0,0) should be (0,0) pixels
    assert hex_geo.to_pixel(0, 0) == (0.0, 0.0)

    # Neighbor hex (0,1)
    # y = size * sqrt(3) * (1 + 0) = spacing
    # x = size * 1.5 * 0 = 0
    px, py = hex_geo.to_pixel(0, 1)
    assert pytest.approx(px) == 0.0
    assert pytest.approx(py) == spacing


def test_hex_rounding():
    spacing = 100.0
    hex_geo = PointyTopHex(spacing)

    # Near (0,0)
    assert hex_geo.round(0.1, 0.1) == (0, 0)
    assert hex_geo.round(-0.4, 0.4) == (0, 0)

    # Near (1,0)
    assert hex_geo.round(0.8, 0.1) == (1, 0)

    # Near (0,1)
    assert hex_geo.round(0.1, 0.9) == (0, 1)
