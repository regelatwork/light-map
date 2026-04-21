from light_map.visibility.visibility_engine import VisibilityEngine, MASK_VALUE_LOW
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def test_low_object_mask_rendering():
    # Setup engine with standard grid spacing
    engine = VisibilityEngine(grid_spacing_svg=10.0)

    # Define a square low object (10x10 in SVG units)
    # Mask scale is 16 / 10 = 1.6
    # 10 * 1.6 = 16 pixels
    low_object = VisibilityBlocker(
        points=[(0, 0), (10, 0), (10, 10), (0, 10)],
        type=VisibilityType.LOW_OBJECT,
        layer_name="Objects",
    )

    # Update blockers (16x16 mask)
    engine.update_blockers([low_object], mask_width=16, mask_height=16)

    # Verify the mask value at the center
    assert engine.blocker_mask[8, 8] == 50
    assert MASK_VALUE_LOW == 50


def test_low_object_priority():
    # Verify that LOW_OBJECT is rendered before WALL
    # We place a WALL over a LOW_OBJECT. Since WALL has higher priority (rendered later),
    # it should overwrite the LOW_OBJECT in the blocker mask.
    engine = VisibilityEngine(grid_spacing_svg=10.0)

    low_object = VisibilityBlocker(
        points=[(0, 0), (10, 0), (10, 10), (0, 10)],
        type=VisibilityType.LOW_OBJECT,
        layer_name="Objects",
    )

    wall = VisibilityBlocker(
        points=[(5, 0), (5, 10)],  # Vertical wall through the middle
        type=VisibilityType.WALL,
        layer_name="Walls",
    )

    engine.update_blockers([low_object, wall], mask_width=16, mask_height=16)

    # Wall should be 255
    # (5 * 1.6 = 8)
    assert engine.blocker_mask[5, 8] == 255

    # Non-wall area should still be 50
    assert engine.blocker_mask[5, 2] == 50
