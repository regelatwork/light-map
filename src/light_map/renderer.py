import cv2
import numpy as np
from .menu_system import MenuState
from .menu_config import MenuColors


class Renderer:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.colors = MenuColors()

    def render(
        self, state: MenuState, background: np.ndarray = None, map_opacity: float = 1.0
    ) -> np.ndarray:
        """
        Renders the current menu state onto an image.

        Args:
            state: The current menu state.
            background: Optional BGR image to use as background. If None, creates a black image.
            map_opacity: Opacity of the background map (0.0 to 1.0).
        """
        if background is not None and map_opacity > 0.0:
            # Create a copy to avoid modifying the original background
            if map_opacity < 1.0:
                # Dim the background
                # dst = src1*alpha + src2*beta + gamma
                # We want: background * opacity + black * (1-opacity)
                # simpler: background * opacity
                image = cv2.convertScaleAbs(background, alpha=map_opacity, beta=0)
            else:
                image = background.copy()
        else:
            image = np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)

        if not state.is_visible:
            return image

        for i, item in enumerate(state.active_items):
            rect = state.item_rects[i]
            x, y, w, h = rect

            # Default Style
            border_color = self.colors.BORDER
            border_thickness = 2
            text_color = self.colors.TEXT

            # Hovered Style
            if i == state.hovered_item_index:
                border_color = self.colors.HOVER
                border_thickness = 4  # Thicker border
                text_color = self.colors.HOVER  # Optional: Match text color

            # Feedback Style (Overrides Hover)
            if i == state.feedback_item_index:
                border_color = self.colors.CONFIRM
                border_thickness = 6
                text_color = self.colors.CONFIRM

            # Draw Item (No Fill to avoid projection interference)
            cv2.rectangle(image, (x, y), (x + w, y + h), border_color, border_thickness)

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
