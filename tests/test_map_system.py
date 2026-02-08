import pytest
from light_map.map_system import MapSystem


@pytest.fixture
def map_system():
    return MapSystem(screen_width=1000, screen_height=1000)


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
