from typing import List
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState
from .menu_config import MenuColors


class MenuLayer(Layer):
    """
    Renders menu items from MenuState.
    Returns a list of small patches, one per menu item.
    Uses menu_timestamp for caching.
    """

    def __init__(self):
        super().__init__(layer_mode=LayerMode.NORMAL)
        self.colors = MenuColors()
        self._cached_patches: List[ImagePatch] = []

    def render(self, state: WorldState) -> List[ImagePatch]:
        menu = state.menu_state
        if not menu or not menu.is_visible:
            return []

        # Cache Check
        if (
            state.menu_timestamp <= self.last_rendered_timestamp
            and self._cached_patches
        ):
            return self._cached_patches

        # Re-render all patches
        new_patches = []

        for i, item in enumerate(menu.active_items):
            rect = menu.item_rects[i]
            x, y, w, h = rect

            # Create small patch buffer for this item
            # Use BGRA to support transparency
            patch_data = np.zeros((h, w, 4), dtype=np.uint8)

            # Default Style
            border_color = self.colors.BORDER
            border_thickness = 2
            text_color = self.colors.TEXT

            # Hovered Style
            if i == menu.hovered_item_index:
                border_color = self.colors.HOVER
                border_thickness = 4
                text_color = self.colors.HOVER

            # Feedback Style (Overrides Hover)
            if i == menu.feedback_item_index:
                border_color = self.colors.CONFIRM
                border_thickness = 6
                text_color = self.colors.CONFIRM

            # Draw onto local patch (0,0 is top-left of patch)
            # BGR channels
            cv2.rectangle(patch_data, (0, 0), (w, h), border_color, border_thickness)

            # Text
            cv2.putText(
                patch_data,
                item.title,
                (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                text_color,
                2,
            )

            # Set Alpha: Opaque where there is color, transparent elsewhere?
            # Actually, for buttons with borders, the center is transparent.
            # But wait, No Fill was the rule.
            # We can use the presence of color as alpha?
            # Or just make the whole button rectangle opaque?
            # The original code just drew on the background.
            # If we want the SAME effect (no fill), we only set alpha where we drew.

            # Simple approach: anywhere B+G+R > 0, set alpha to 255
            # This makes the border and text opaque, and the background transparent.
            mask = np.any(patch_data[:, :, :3] > 0, axis=2)
            patch_data[mask, 3] = 255

            new_patches.append(ImagePatch(x=x, y=y, width=w, height=h, data=patch_data))

        self._cached_patches = new_patches
        self.last_rendered_timestamp = state.menu_timestamp
        return self._cached_patches
