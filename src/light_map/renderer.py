from typing import Optional, List, Any
import cv2
import numpy as np
from .menu_system import MenuState
from .menu_config import MenuColors
from .common_types import Layer, LayerMode, ImagePatch


class Renderer:
    """
    Coordinates the compositing of multiple visual layers into a final frame.
    """

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.colors = MenuColors()
        self.output_buffer = np.zeros(
            (self.screen_height, self.screen_width, 3), dtype=np.uint8
        )

    def render(self, state: Any, layers: List[Layer]) -> np.ndarray:
        """
        Composites all provided layers into the final output buffer.

        Args:
            state: The current WorldState.
            layers: A list of Layer objects, from bottom to top.
        """
        # Clear buffer (or we could rely on a BLOCKING background layer at the bottom)
        self.output_buffer.fill(0)

        for layer in layers:
            patches = layer.render(state)
            if not patches:
                continue

            for patch in patches:
                self._composite_patch(patch, layer.layer_mode)

        return self.output_buffer

    def _composite_patch(self, patch: ImagePatch, mode: LayerMode):
        """Internal helper to blend a patch onto the output buffer."""
        # Bound checks
        x1, y1 = max(0, patch.x), max(0, patch.y)
        x2, y2 = (
            min(self.screen_width, patch.x + patch.width),
            min(self.screen_height, patch.y + patch.height),
        )

        if x1 >= x2 or y1 >= y2:
            return

        # Slice patch data if it's partially off-screen
        # (Assuming patch.data matches patch.width/height)
        px1, py1 = x1 - patch.x, y1 - patch.y
        px2, py2 = px1 + (x2 - x1), py1 + (y2 - y1)
        patch_slice = patch.data[py1:py2, px1:px2]

        if mode == LayerMode.BLOCKING:
            # Fast slice assignment (ignore alpha)
            self.output_buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
        else:
            # NORMAL mode: Alpha blending
            # Final = (Patch * Alpha) + (Buffer * (1 - Alpha))
            alpha = patch_slice[:, :, 3:4] / 255.0
            roi = self.output_buffer[y1:y2, x1:x2]
            blended = (patch_slice[:, :, :3] * alpha + roi * (1.0 - alpha)).astype(
                np.uint8
            )
            self.output_buffer[y1:y2, x1:x2] = blended

    def render_legacy(
        self,
        state: Optional[MenuState],
        background: np.ndarray = None,
        map_opacity: float = 1.0,
    ) -> np.ndarray:
        """
        Original monolithic rendering logic. Kept for transition.
        """
        if background is not None and map_opacity > 0.0:
            if map_opacity < 1.0:
                image = cv2.convertScaleAbs(background, alpha=map_opacity, beta=0)
            else:
                image = background.copy()
        else:
            image = np.zeros((self.screen_height, self.screen_width, 3), dtype=np.uint8)

        if state is None or not state.is_visible:
            return image

        for i, item in enumerate(state.active_items):
            rect = state.item_rects[i]
            x, y, w, h = rect

            border_color = self.colors.BORDER
            border_thickness = 2
            text_color = self.colors.TEXT

            if i == state.hovered_item_index:
                border_color = self.colors.HOVER
                border_thickness = 4
                text_color = self.colors.HOVER

            if i == state.feedback_item_index:
                border_color = self.colors.CONFIRM
                border_thickness = 6
                text_color = self.colors.CONFIRM

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


# Maintain original method name for backward compatibility until integration
Renderer.render_monolithic = Renderer.render_legacy
