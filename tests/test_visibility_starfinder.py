import pytest
import numpy as np
import cv2
from light_map.visibility_engine import VisibilityEngine
from light_map.visibility_types import VisibilityType, VisibilityBlocker


def test_starfinder_origin_points_count(mocker):
    # Mock calculate_visibility to count how many times it's called
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    spy = mocker.spy(engine, 'calculate_visibility')
    
    # 1x1 token: 1 center + (1+1)^2 = 5 points
    engine.get_token_vision_mask(1, 50, 50, 1, 10, 100, 100)
    assert spy.call_count == 5
    
    spy.reset_mock()
    # 2x2 token: 1 center + (2+1)^2 = 10 points
    engine.get_token_vision_mask(2, 50, 50, 2, 10, 100, 100)
    assert spy.call_count == 10


def test_starfinder_see_around_corners():
    # Place a wall that blocks the center but not the corners
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    # Wall right in front of the center (50, 50), at x=55
    # For a 1x1 token (size 1), corners are at x=45 and x=55
    # Wait, if center is at 50, corners are 50 +/- 5
    # Let's put a small wall at (52, 48) to (52, 52)
    wall = VisibilityBlocker(
        segments=[(52, 48), (52, 52)],
        type=VisibilityType.WALL,
        layer_name="Wall"
    )
    engine.update_blockers([wall])
    
    # Single point at (50, 50) would have a shadow
    mask_single = np.zeros((100, 100), dtype=np.uint8)
    poly = engine.calculate_visibility((50, 50), 100)
    # Scale: 16/10 = 1.6
    scaled_poly = [(int(p[0]*1.6), int(p[1]*1.6)) for p in poly]
    cv2.fillPoly(mask_single, [np.array(scaled_poly, dtype=np.int32)], 255)
    
    # Multi-point token at (50, 50) size 1
    mask_multi = engine.get_token_vision_mask(1, 50, 50, 1, 10, 160, 160)
    
    # The multi-point mask should have more "visible" pixels because corners can see past the small wall
    assert np.sum(mask_multi > 0) > np.sum(mask_single > 0)


def test_starfinder_oob_safety():
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    # Token way off map
    mask = engine.get_token_vision_mask(1, -1000, -1000, 1, 10, 100, 100)
    # Should be all zeros (or at least not crash)
    assert np.all(mask == 0)
