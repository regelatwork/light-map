from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType


def test_tall_object_first_exit_logic():
    """
    Tests the "First Exit" LOS logic for tall objects.
    - Ground -> Plateau (Top visible)
    - Ground -> Behind (Blocked)
    - Plateau -> Ground (Visible)
    """
    # Initialize engine with 16 units per grid cell
    engine = VisibilityEngine(grid_spacing_svg=1.0)

    # Define a tall object: a 5x5 square from (10, 10) to (15, 15)
    tall_blocker = VisibilityBlocker(
        id="plateau",
        points=[(10, 10), (15, 10), (15, 15), (10, 15), (10, 10)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="tall",
    )

    # Update blockers (mask scale is 16.0 by default)
    # We need to provide mask dimensions
    engine.update_blockers([tall_blocker], mask_width=400, mask_height=400)

    # Scenario 1: Ground -> Plateau (Top visible)
    # Viewer at (5, 5), Target at (12, 12)
    # This should be VISIBLE because it enters TALL but doesn't exit it.
    mask_visible, _ = engine.get_token_vision_mask(
        token_id=1,
        origin_x=5.0,
        origin_y=5.0,
        size=1,
        vision_range_grid=50.0,
        mask_width=400,
        mask_height=400,
    )

    target_mx = int(12.0 * engine.svg_to_mask_scale)
    target_my = int(12.0 * engine.svg_to_mask_scale)
    assert mask_visible[target_my, target_mx] == 255, (
        "Plateau top should be visible from ground"
    )

    # Scenario 2: Ground -> Behind (Blocked)
    # Viewer at (5, 5), Target at (20, 20)
    # Line goes through (10, 10)-(15, 15).
    # It enters TALL and then exits TALL. Since it started in OPEN, the exit is blocked.
    target_mx2 = int(20.0 * engine.svg_to_mask_scale)
    target_my2 = int(20.0 * engine.svg_to_mask_scale)
    assert mask_visible[target_my2, target_mx2] == 0, (
        "Area behind plateau should be blocked from ground"
    )

    # Scenario 3: Plateau -> Ground (Visible)
    # Viewer at (12, 12), Target at (5, 5)
    # Starts in TALL, exits to OPEN. This is the "First Exit", so it should be VISIBLE.
    mask_visible_from_top, _ = engine.get_token_vision_mask(
        token_id=2,
        origin_x=12.0,
        origin_y=12.0,
        size=1,
        vision_range_grid=50.0,
        mask_width=400,
        mask_height=400,
    )

    ground_mx = int(5.0 * engine.svg_to_mask_scale)
    ground_my = int(5.0 * engine.svg_to_mask_scale)
    assert mask_visible_from_top[ground_my, ground_mx] == 255, (
        "Ground should be visible from plateau top"
    )


def test_tall_object_multiple_exit_blocking():
    """
    Tests that multiple exits from tall objects are blocked.
    - Start in TALL1 -> Exit to OPEN (OK) -> Enter TALL2 -> Exit to OPEN (BLOCKED)
    """
    engine = VisibilityEngine(grid_spacing_svg=1.0)

    # Two tall objects
    blocker1 = VisibilityBlocker(
        id="t1",
        points=[(10, 0), (20, 0), (20, 20), (10, 20), (10, 0)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="tall",
    )
    blocker2 = VisibilityBlocker(
        id="t2",
        points=[(30, 0), (40, 0), (40, 20), (30, 20), (30, 0)],
        type=VisibilityType.TALL_OBJECT,
        layer_name="tall",
    )

    engine.update_blockers([blocker1, blocker2], mask_width=800, mask_height=400)

    # Viewer inside T1 at (15, 10)
    # Target in OPEN between them at (25, 10) -> Should be VISIBLE (1st exit)
    # Target inside T2 at (35, 10) -> Should be VISIBLE (2nd entry)
    # Target beyond T2 at (45, 10) -> Should be BLOCKED (2nd exit)

    mask, _ = engine.get_token_vision_mask(
        token_id=3,
        origin_x=15.0,
        origin_y=10.0,
        size=1,
        vision_range_grid=100.0,
        mask_width=800,
        mask_height=400,
    )

    def get_m(x, y):
        return int(y * 16), int(x * 16)

    my1, mx1 = get_m(25.0, 10.0)
    my2, mx2 = get_m(35.0, 10.0)
    my3, mx3 = get_m(45.0, 10.0)

    assert mask[my1, mx1] == 255, (
        "Gap between tall objects should be visible from first tall object"
    )
    assert mask[my2, mx2] == 255, (
        "Second tall object top should be visible from first tall object"
    )
    assert mask[my3, mx3] == 0, "Area beyond second tall object should be blocked"
