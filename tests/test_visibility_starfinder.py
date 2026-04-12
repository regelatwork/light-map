import numpy as np
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker


def test_starfinder_see_around_corners():
    # Place a wall that blocks the center but not the corners
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    # 100 svg = 16 px.
    # Wall right in front of the center (100, 100) svg -> (16, 16) px.
    # Wall from (110, 90) to (110, 110) svg -> (17.6, 14.4) to (17.6, 17.6) px.
    # Center (16, 16). Radius for size 1 is 8px.
    # Corners are at x=8, 24.
    wall = VisibilityBlocker(
        points=[(110, 90), (110, 110)], type=VisibilityType.WALL, layer_name="Wall"
    )
    mask_w, mask_h = 256, 256
    engine.update_blockers([wall], mask_width=mask_w, mask_height=mask_h)

    # Multi-point token at (100, 100) size 1
    # Footprint will allow peeking around this small wall
    mask_multi = engine.get_token_vision_mask(1, 100, 100, 1, 10, mask_w, mask_h)

    # Point directly behind the small wall: (120, 100) svg -> (19.2, 16) px
    # Since it's a size 1 token, its edge can reach y=100-50=50 to y=100+50=150.
    # The wall is only y=90 to y=110.
    # So a point at y=100, x=110 should be visible from e.g. (90, 120) footprint?
    # Wait, the token footprint is +/- 8px + 1px = 9px from center.
    # Center (16, 16). Footprint reaches y=7..25.
    # Wall is at x=17.6, y=14.4..17.6.
    # So source point at y=20, x=16 can see y=16, x=19 because wall ends at y=17.6.
    assert mask_multi[16, 19] > 0


def test_starfinder_oob_safety():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    engine.update_blockers([], mask_width=100, mask_height=100)
    # Token way off map
    mask = engine.get_token_vision_mask(1, -1000, -1000, 1, 10, 100, 100)
    # Should be all zeros (or at least not crash)
    assert np.all(mask == 0)
