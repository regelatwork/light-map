import pytest
import numpy as np
from light_map.map_system import MapSystem


@pytest.fixture
def map_system():
    from light_map.common_types import AppConfig

    config = AppConfig(width=1000, height=1000, projector_matrix=np.eye(3))
    return MapSystem(config)


def test_initial_state(map_system):
    assert map_system.state.x == 0.0
    assert map_system.state.y == 0.0
    assert map_system.state.zoom == 1.0
    assert map_system.state.rotation == 0.0


def test_pan(map_system):
    map_system.pan(10, -20)
    assert map_system.state.x == 10.0
    assert map_system.state.y == -20.0

    map_system.pan(5, 5)
    assert map_system.state.x == 15.0
    assert map_system.state.y == -15.0


def test_zoom_simple(map_system):
    map_system.zoom(1.5)
    assert map_system.state.zoom == 1.5

    map_system.zoom(0.5)
    assert map_system.state.zoom == 0.75


def test_zoom_at_point(map_system):
    # Zooming into point (100, 100)
    # Initial: x=0, y=0, zoom=1
    # Zoom factor 2.0
    # Expected pan: new_pan = center - (center - old_pan) * ratio
    # x = 100 - (100 - 0) * 2 = 100 - 200 = -100
    map_system.zoom(2.0, center_x=100, center_y=100)

    assert map_system.state.zoom == 2.0
    assert map_system.state.x == -100.0
    assert map_system.state.y == -100.0


def test_rotate(map_system):
    map_system.rotate(90)
    assert map_system.state.rotation == 90.0

    map_system.rotate(90)
    assert map_system.state.rotation == 180.0

    map_system.rotate(180)
    assert map_system.state.rotation == 0.0  # Wraps at 360

    map_system.rotate(-90)
    assert map_system.state.rotation == 270.0


def test_get_render_params(map_system):
    map_system.set_state(10, 20, 1.5, 90)
    params = map_system.get_render_params()

    assert params["scale_factor"] == 1.5
    assert params["offset_x"] == 10
    assert params["offset_y"] == 20
    assert params["rotation"] == 90.0


def test_reset_view(map_system):
    map_system.set_state(100, 100, 2.0, 180)
    map_system.reset_view()

    assert map_system.state.x == 0.0
    assert map_system.state.zoom == 1.0


def test_reset_zoom_to_base_pivots_around_center(map_system):
    """Test that resetting zoom preserves the center point."""
    map_system.base_scale = 1.0
    # Screen center is (500, 500)

    # 1. Set state so World (100, 100) is at Screen (500, 500) with Zoom 1.0
    # Screen = World * Zoom + Pan
    # 500 = 100 * 1.0 + Pan => Pan = 400
    map_system.set_state(400, 400, 1.0, 0.0)

    # Verify setup
    wx, wy = map_system.screen_to_world(500, 500)
    assert wx == 100.0
    assert wy == 100.0

    # 2. Zoom in to 2.0 around center (simulating user action)
    map_system.zoom(2.0, center_x=500, center_y=500)
    assert map_system.state.zoom == 2.0

    # Verify center is still World (100, 100)
    wx_new, wy_new = map_system.screen_to_world(500, 500)
    assert wx_new == 100.0
    assert wy_new == 100.0

    # Pan should have changed to 300 (see thought process)
    # 500 = 100 * 2.0 + Pan => Pan = 300
    assert map_system.state.x == 300.0
    assert map_system.state.y == 300.0

    # 3. Reset zoom to base (1.0)
    map_system.reset_zoom_to_base()
    assert map_system.state.zoom == 1.0

    # 4. Verify center is still World (100, 100)
    wx_final, wy_final = map_system.screen_to_world(500, 500)
    assert wx_final == 100.0
    assert wy_final == 100.0

    # Pan should return to 400
    assert map_system.state.x == 400.0
    assert map_system.state.y == 400.0
