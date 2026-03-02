import pytest
import numpy as np
from light_map.renderer import Renderer


@pytest.fixture
def mock_menu_state():
    # Minimal mock for MenuState
    class MockState:
        is_visible = False
        active_items = []
        item_rects = []
        hovered_item_index = -1
        feedback_item_index = -1

    return MockState()


def test_render_opacity_zero(mock_menu_state):
    renderer = Renderer(100, 100)
    bg = np.full((100, 100, 3), 255, dtype=np.uint8)  # White

    # Opacity 0 -> Output should be black
    out = renderer.render_legacy(mock_menu_state, background=bg, map_opacity=0.0)
    assert np.mean(out) == 0


def test_render_opacity_full(mock_menu_state):
    renderer = Renderer(100, 100)
    bg = np.full((100, 100, 3), 255, dtype=np.uint8)

    # Opacity 1 -> Output should be white (unchanged)
    out = renderer.render_legacy(mock_menu_state, background=bg, map_opacity=1.0)
    assert np.mean(out) == 255


def test_render_opacity_half(mock_menu_state):
    renderer = Renderer(100, 100)
    bg = np.full((100, 100, 3), 200, dtype=np.uint8)

    # Opacity 0.5 -> Output should be dimmed (around 100)
    out = renderer.render_legacy(mock_menu_state, background=bg, map_opacity=0.5)
    mean = np.mean(out)
    assert 99 <= mean <= 101  # Allow slight rounding error


def test_render_no_background_ignores_opacity(mock_menu_state):
    renderer = Renderer(100, 100)
    # No background provided -> Black by default
    out = renderer.render_legacy(mock_menu_state, background=None, map_opacity=0.5)
    assert np.mean(out) == 0
