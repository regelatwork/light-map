from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def test_blocker_mask_watertight_rendering():
    # 100 svg units = 16 pixels.
    engine = VisibilityEngine(grid_spacing_svg=100.0)

    # Create two points that almost touch but have a tiny gap
    # x=49.5 (svg) = 7.92px -> 7px or 8px
    # x=50.5 (svg) = 8.08px -> 8px or 9px
    # A gap at 50 svg units = 8 pixels.
    blocker = VisibilityBlocker(
        points=[(0, 0), (49.5, 0), (50.5, 0), (100, 0)],
        type=VisibilityType.WALL,
        layer_name="walls",
    )
    # We need to tell the engine the mask size for rendering
    mask_w, mask_h = 200, 200
    engine.update_blockers([blocker], mask_width=mask_w, mask_height=mask_h)

    # Check if the gap at x=50 (pixel 8) is closed in the blocker mask
    # Note: cv2 coordinates are (x, y), numpy are (y, x)
    assert engine.blocker_mask[0, 8] > 0
