from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def test_watertight_blocking():
    # 100 svg = 16 px.
    engine = VisibilityEngine(grid_spacing_svg=100.0)

    # Long horizontal wall: (0, 100) to (300, 100)
    blockers = [
        VisibilityBlocker(
            points=[(0, 100), (300, 100)],
            type=VisibilityType.WALL,
            layer_name="walls",
        )
    ]

    mask_w, mask_h = 256, 256
    engine.update_blockers(blockers, mask_width=mask_w, mask_height=mask_h)

    # Token at (100, 50) svg. Well above the wall at y=100.
    mask, _ = engine.get_token_vision_mask(
        token_id=1,
        origin_x=100.0,
        origin_y=50.0,
        size=1,
        vision_range_grid=10.0,
        mask_width=mask_w,
        mask_height=mask_h,
    )

    # Above wall: visible
    assert mask[8, 16] > 0  # (50, 100) svg
    # Below wall: blocked
    assert mask[24, 16] == 0  # (150, 100) svg


def test_corner_peeking():
    engine = VisibilityEngine(grid_spacing_svg=100.0)
    # L-shape corner at (100, 100)
    blockers = [
        VisibilityBlocker(
            points=[(0, 100), (100, 100)],
            type=VisibilityType.WALL,
            layer_name="walls",
        ),
        VisibilityBlocker(
            points=[(100, 100), (100, 200)],
            type=VisibilityType.WALL,
            layer_name="walls",
        ),
    ]
    mask_w, mask_h = 256, 256
    engine.update_blockers(blockers, mask_width=mask_w, mask_height=mask_h)

    # Token near the corner but slightly above/left
    # (90, 90) svg. Footprint should reach the corner (100, 100)
    mask, _ = engine.get_token_vision_mask(
        token_id=1,
        origin_x=90.0,
        origin_y=90.0,
        size=1,
        vision_range_grid=5.0,
        mask_width=mask_w,
        mask_height=mask_h,
    )

    # Point around the corner: (110, 110) svg
    # Should be visible due to corner peeking
    assert mask[18, 18] > 0
