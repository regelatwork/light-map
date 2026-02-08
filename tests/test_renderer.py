import unittest
import numpy as np
from src.light_map.renderer import Renderer
from src.light_map.menu_system import MenuState
from src.light_map.common_types import MenuItem


class TestRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = Renderer(800, 600)

    def test_render_not_visible(self):
        # Create a MenuState that is not visible
        state = MenuState(
            current_menu_title="Main Menu",
            active_items=[],
            item_rects=[],
            hovered_item_index=None,
            prime_progress=0.0,
            summon_progress=0.0,
            just_triggered_action=None,
            cursor_pos=None,
            is_visible=False,
        )

        # Render the menu
        image = self.renderer.render(state)

        # Check that the image is black
        self.assertTrue(np.all(image == 0))

    def test_render_visible_with_hover(self):
        # Create a MenuState that is visible
        items = [
            MenuItem(title="Item 1", action_id="action1"),
            MenuItem(title="Item 2", action_id="action2"),
        ]
        rects = [
            (100, 100, 200, 50),
            (100, 160, 200, 50),
        ]
        state = MenuState(
            current_menu_title="Main Menu",
            active_items=items,
            item_rects=rects,
            hovered_item_index=0,  # Item 1 is hovered
            prime_progress=0.0,
            summon_progress=0.0,
            just_triggered_action=None,
            cursor_pos=(150, 125),
            is_visible=True,
        )

        # Render the menu
        image = self.renderer.render(state)

        # Check that the image is not black
        self.assertFalse(np.all(image == 0))


if __name__ == "__main__":
    unittest.main()
