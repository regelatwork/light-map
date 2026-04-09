import numpy as np
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker


def test_visibility_empty_room():
    # 100 svg = 16 px
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    mask_w, mask_h = 200, 200
    engine.update_blockers([], mask_width=mask_w, mask_height=mask_h)

    # Token at (100, 100) svg -> (16, 16) pixels
    # Vision range 5 grids = 80 px
    mask = engine.get_token_vision_mask(
        token_id=1,
        origin_x=100.0,
        origin_y=100.0,
        size=1,
        vision_range_grid=5.0,
        mask_width=mask_w,
        mask_height=mask_h,
    )

    # Should be a circle-like area
    # Center (16, 16). Radius 80.
    # Check point inside: (16+40, 16+40) = (56, 56)
    assert mask[56, 56] > 0
    # Check point outside: (16+90, 16) = (106, 16)
    assert mask[16, 106] == 0


def test_visibility_blocked_by_wall():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    # A wall at x=150 (svg) = 24px from y=0 to y=200
    wall = VisibilityBlocker(
        segments=[(150, 0), (150, 200)], type=VisibilityType.WALL, layer_name="Walls"
    )
    mask_w, mask_h = 200, 200
    engine.update_blockers([wall], mask_width=mask_w, mask_height=mask_h)

    # Token at (100, 100) svg -> (16, 16) pixels
    # Wall is at x=24.
    mask = engine.get_token_vision_mask(
        token_id=1,
        origin_x=100.0,
        origin_y=100.0,
        size=1,
        vision_range_grid=10.0,
        mask_width=mask_w,
        mask_height=mask_h,
    )

    # Point before wall: (20, 16) -> (125 svg, 100 svg)
    assert mask[16, 20] > 0
    # Point after wall: (28, 16) -> (175 svg, 100 svg)
    assert mask[16, 28] == 0


def test_visibility_door_toggle():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    door = VisibilityBlocker(
        segments=[(150, 0), (150, 200)],
        type=VisibilityType.DOOR,
        layer_name="Doors",
        is_open=False,
    )
    mask_w, mask_h = 200, 200
    engine.update_blockers([door], mask_width=mask_w, mask_height=mask_h)

    # Token at (100, 100)
    # Door closed: blocked
    mask_closed = engine.get_token_vision_mask(1, 100, 100, 1, 10, mask_w, mask_h)
    assert mask_closed[16, 28] == 0

    # Open door
    door.is_open = True
    # Re-update blockers to rebuild mask
    engine.update_blockers([door], mask_width=mask_w, mask_height=mask_h)

    mask_open = engine.get_token_vision_mask(1, 100, 100, 1, 10, mask_w, mask_h)
    assert mask_open[16, 28] > 0


def test_visibility_cache_hysteresis():
    engine = VisibilityEngine(grid_spacing_svg=100.0, grid_origin=(0, 0))
    mask_w, mask_h = 200, 200
    engine.update_blockers([], mask_width=mask_w, mask_height=mask_h)

    token_id = 1
    # Both in Grid (1, 1) assuming grid spacing is 100
    origin1 = (120, 120)
    mask1 = engine.get_token_vision_mask(
        token_id, origin1[0], origin1[1], 1, 5, mask_w, mask_h
    )

    assert len(engine.mask_cache) == 1

    # Move slightly within the same grid cell
    origin2 = (140, 140)
    mask2 = engine.get_token_vision_mask(
        token_id, origin2[0], origin2[1], 1, 5, mask_w, mask_h
    )

    # Should be identical from cache
    assert np.array_equal(mask1, mask2)
    assert len(engine.mask_cache) == 1

    # Move to next cell
    origin3 = (220, 120)  # Grid (2, 1)
    mask3 = engine.get_token_vision_mask(
        token_id, origin3[0], origin3[1], 1, 5, mask_w, mask_h
    )
    assert not np.array_equal(mask1, mask3)
    assert len(engine.mask_cache) == 2
