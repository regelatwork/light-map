import numpy as np
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def test_size_3_token_corner_peeking():
    # 100 svg = 16 px.
    engine = VisibilityEngine(grid_spacing_svg=100.0)

    # L-shape corner at (400, 400) svg -> (64, 64) px.
    # Token Size 3 at (200, 200) svg -> (32, 32) px.
    # Wall 1: (0, 400) to (400, 400) -> y=64, x=0..64
    # Wall 2: (400, 400) to (400, 800) -> x=64, y=64..128
    blockers = [
        VisibilityBlocker(
            segments=[(0, 400), (400, 400)],
            type=VisibilityType.WALL,
            layer_name="walls",
        ),
        VisibilityBlocker(
            segments=[(400, 400), (400, 800)],
            type=VisibilityType.WALL,
            layer_name="walls",
        ),
    ]

    mask_w, mask_h = 1024, 1024
    engine.update_blockers(blockers, mask_width=mask_w, mask_height=mask_h)

    # Token Size 3 at (200, 200) svg.
    # cx, cy = (32, 32)
    # Range limit = 25px.
    # Footprint should reach x=32+25=57, y=32+25=57.
    # Wall is at x=64, y=64.
    # So the token is completely contained in the top-left quadrant.

    mask = engine.get_token_vision_mask(
        token_id=50,
        origin_x=200.0,
        origin_y=200.0,
        size=3,
        vision_range_grid=10.0,
        mask_width=mask_w,
        mask_height=mask_h,
    )

    # 1. Directly visible
    assert mask[32, 32] > 0

    # 2. Around the corner: (500, 500) svg -> (80, 80) px
    # Corner is at (64, 64). Footprint reaches (57, 57).
    # From (57, 57) it can see (80, 80).
    assert mask[80, 80] > 0

    # 3. Blocked: (100, 600) svg -> (16, 96) px
    # To see (16, 96) from footprint [0..57, 0..57], it must cross y=64.
    assert mask[96, 16] == 0


def test_size_3_token_footprint_bounds():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    # 100 svg = 16 px.
    # Size 3 = 48px wide. Radius = 24px. Overhang +1px = 25px radius.
    engine.blocker_mask = np.zeros((100, 100), dtype=np.uint8)

    # Center (50, 50).
    # Footprint should reach (50-25, 50-25) to (50+25, 50+25) = (25, 25) to (75, 75)
    footprint = engine._calculate_token_footprint(50, 50, size=3)

    coords = np.where(footprint > 0)
    assert np.min(coords[1]) == 25
    assert np.max(coords[1]) == 75
    assert np.min(coords[0]) == 25
    assert np.max(coords[0]) == 75
