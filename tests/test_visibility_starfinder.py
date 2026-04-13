import numpy as np
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker


def test_starfinder_see_around_corners():
    # Place a wall that blocks the center but not the corners
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    # 100 svg = 16 px.
    # Wall right in front of the center (100, 100) svg -> (16, 16) px.
    # Wall from (110, 90) to (110, 110) svg -> (17.6, 14.4) to (17.6, 17.6) px.
    wall = VisibilityBlocker(
        points=[(110, 90), (110, 110)], type=VisibilityType.WALL, layer_name="Wall"
    )
    mask_w, mask_h = 256, 256
    engine.update_blockers([wall], mask_width=mask_w, mask_height=mask_h)

    # Multi-point token at (100, 100) size 1
    mask_multi, _ = engine.get_token_vision_mask(1, 100, 100, 1, 10, mask_w, mask_h)

    # Point directly behind the small wall: (120, 100) svg -> (19.2, 16) px
    assert mask_multi[16, 19] > 0


def test_starfinder_oob_safety():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    engine.update_blockers([], mask_width=100, mask_height=100)
    # Token way off map
    mask, _ = engine.get_token_vision_mask(1, -1000, -1000, 1, 10, 100, 100)
    # Should be all zeros (or at least not crash)
    assert np.all(mask == 0)
