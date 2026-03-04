import pytest
import math
from light_map.visibility_engine import VisibilityEngine
from light_map.visibility_types import VisibilityType, VisibilityBlocker


def test_visibility_empty_room():
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    engine.update_blockers([])

    origin = (50, 50)
    vision_range = 100
    poly = engine.calculate_visibility(origin, vision_range)

    # Should be a circle-like polygon
    assert len(poly) >= 32
    for p in poly:
        dist = math.sqrt((p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
        assert pytest.approx(dist) == vision_range


def test_visibility_blocked_by_wall():
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    # A wall at x=60 from y=0 to y=100
    wall = VisibilityBlocker(
        segments=[(60, 0), (60, 100)], type=VisibilityType.WALL, layer_name="Walls"
    )
    engine.update_blockers([wall])

    origin = (50, 50)
    vision_range = 100

    # Cast a ray to the right (angle 0)
    poly = engine.calculate_visibility(origin, vision_range)

    # Find the point at angle 0 (dx=1, dy=0)
    # The wall is at x=60, origin is at x=50, so dist should be 10
    found_wall_hit = False
    for p in poly:
        angle = math.atan2(p[1] - origin[1], p[0] - origin[0])
        if abs(angle) < 0.001:
            dist = math.sqrt((p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
            assert pytest.approx(dist) == 10
            found_wall_hit = True
            break
    assert found_wall_hit


def test_visibility_door_toggle():
    engine = VisibilityEngine(grid_spacing_svg=10.0)
    door = VisibilityBlocker(
        segments=[(60, 40), (60, 60)],
        type=VisibilityType.DOOR,
        layer_name="Doors",
        is_open=False,
    )
    engine.update_blockers([door])

    origin = (50, 50)
    vision_range = 100

    # Door closed: blocked at dist 10
    poly_closed = engine.calculate_visibility(origin, vision_range)
    for p in poly_closed:
        angle = math.atan2(p[1] - origin[1], p[0] - origin[0])
        if abs(angle) < 0.001:
            dist = math.sqrt((p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
            assert pytest.approx(dist) == 10

    # Open door
    door.is_open = True
    # We must call calculate_visibility again.
    # Note: VisibilityEngine doesn't automatically detect property changes in blockers,
    # but the implementation of calculate_visibility checks blocker.is_open in real-time.
    poly_open = engine.calculate_visibility(origin, vision_range)
    for p in poly_open:
        angle = math.atan2(p[1] - origin[1], p[0] - origin[0])
        if abs(angle) < 0.001:
            dist = math.sqrt((p[0] - origin[0]) ** 2 + (p[1] - origin[1]) ** 2)
            assert pytest.approx(dist) == vision_range


def test_visibility_cache_hysteresis():
    engine = VisibilityEngine(grid_spacing_svg=10.0, grid_origin=(0, 0))
    engine.update_blockers([])

    token_id = 1
    origin1 = (52, 52)  # Grid (5, 5)
    poly1 = engine.calculate_visibility(origin1, 100, token_id=token_id)

    assert len(engine.cache) == 1

    # Move slightly within the same grid cell
    origin2 = (54, 54)  # Still Grid (5, 5)
    poly2 = engine.calculate_visibility(origin2, 100, token_id=token_id)

    # Should be identical points from cache (even though physical origin is different)
    assert poly1 == poly2
    assert len(engine.cache) == 1

    # Move to next cell
    origin3 = (62, 52)  # Grid (6, 5)
    poly3 = engine.calculate_visibility(origin3, 100, token_id=token_id)
    assert poly3 != poly1
    assert len(engine.cache) == 2
