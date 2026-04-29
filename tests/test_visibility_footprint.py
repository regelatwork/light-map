import numpy as np

from light_map.visibility.visibility_engine import VisibilityEngine


def test_token_footprint_expansion():
    # 100 svg = 16 px. Center = 8px.
    engine = VisibilityEngine(grid_spacing_svg=100.0)

    # Create a small blocker mask (32x32)
    # A wall at x=12 (vertical)
    engine.blocker_mask = np.zeros((32, 32), dtype=np.uint8)
    engine.blocker_mask[:, 12] = 255

    # Token size 1 (16px wide, so +/- 8px from center)
    # Expansion +1px means +/- 9px.
    # From x=8, expansion goes to x=17. But wall is at x=12.
    footprint, _ = engine._calculate_token_footprint_with_planes(8, 8, size=1)
    # Should stop at x=11 (just before wall)
    assert np.max(np.where(footprint > 0)[1]) < 12
    # Should reach at least x=11
    assert np.max(np.where(footprint > 0)[1]) == 11


def test_token_footprint_no_wall():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    engine.blocker_mask = np.zeros((32, 32), dtype=np.uint8)

    # Token size 1 (16px) -> +/- 8px.
    # Center (16, 16). Range 8 to 24.
    footprint, _ = engine._calculate_token_footprint_with_planes(16, 16, size=1)

    # Check bounds
    coords = np.where(footprint > 0)
    assert np.min(coords[1]) == 8  # 16 - 8
    assert np.max(coords[1]) == 24  # 16 + 8
    assert np.min(coords[0]) == 8
    assert np.max(coords[0]) == 24
