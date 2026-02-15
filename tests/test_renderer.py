import pytest
import numpy as np
from light_map.renderer import Renderer
from light_map.menu_system import MenuState, MenuItem


@pytest.fixture
def renderer():
    return Renderer(800, 600)


@pytest.fixture
def visible_state():
    items = [
        MenuItem(title="Item 1", action_id="action1"),
        MenuItem(title="Item 2", action_id="action2"),
    ]
    rects = [
        (100, 100, 200, 50),
        (100, 160, 200, 50),
    ]
    return MenuState(
        current_menu_title="Main Menu",
        active_items=items,
        item_rects=rects,
        hovered_item_index=0,  # Item 1 is hovered
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        just_triggered_action=None,
        cursor_pos=(150, 125),
        is_visible=True,
    )


def test_render_not_visible(renderer):
    # Create a MenuState that is not visible
    state = MenuState(
        current_menu_title="Main Menu",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        just_triggered_action=None,
        cursor_pos=None,
        is_visible=False,
    )

    # Render the menu
    image = renderer.render(state)

    # Check that the image is black
    assert np.all(image == 0)


def test_render_visible_with_hover(renderer, visible_state):
    # Render the menu
    image = renderer.render(visible_state)

    # Check that the image is not black
    assert not np.all(image == 0)


def test_render_with_background(renderer, visible_state):
    # Create a background (e.g., solid red)
    bg = np.zeros((600, 800, 3), dtype=np.uint8)
    bg[:, :] = (0, 0, 255)  # Red in BGR

    # Render with background
    image = renderer.render(visible_state, background=bg)

    # Check that the background is still visible outside menu rects
    # Menu rects are at (100, 100) -> (300, 150)
    # Check a point clearly outside: (50, 50)
    assert np.array_equal(image[50, 50], [0, 0, 255])

    # Check that menu is drawn over background
    # Since we use No Fill now, the center should be the original background
    assert np.array_equal(image[125, 150], [0, 0, 255])

    # But the BORDER should be changed (Item 1 rect: (100, 100, 200, 50))
    # Border at Y=100
    assert not np.array_equal(image[100, 150], [0, 0, 255])
