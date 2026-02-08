import cv2
import numpy as np
from .menu_system import MenuState
from .menu_config import MenuColors


class Renderer:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.colors = MenuColors()

    def render(self, state: MenuState, background: np.ndarray = None) -> np.ndarray:
        """
        Renders the current menu state onto an image.

        Args:
            state: The current menu state.
            background: Optional BGR image to use as background. If None, creates a black image.
        """
        if background is not None:
            # Create a copy to avoid modifying the original background
            image = background.copy()
        else:
            image = np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)

        if not state.is_visible:
            return image

        for i, item in enumerate(state.active_items):
            rect = state.item_rects[i]
            x, y, w, h = rect

            color = self.colors.NORMAL
            if i == state.hovered_item_index:
                color = self.colors.HOVER

            cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)

            text_color = self.colors.TEXT
            cv2.putText(
                image,
                item.title,
                (x + 10, y + h - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                text_color,
                2,
            )

        return image
