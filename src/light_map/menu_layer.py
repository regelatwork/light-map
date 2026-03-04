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

    def __init__(self, state: WorldState):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.colors = MenuColors()
        self._last_visible = False

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True

        menu = self.state.menu_state
        visible = menu.is_visible if menu else False

        if visible != self._last_visible:
            return True

        if not visible:
            return False

        return self.state.menu_timestamp > self._last_state_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []

        menu = self.state.menu_state
        self._last_visible = menu.is_visible if menu else False

        if not self._last_visible:
            return []

        # Re-render all patches
        new_patches = []

        for i, item in enumerate(menu.active_items):
            rect = menu.item_rects[i]
            x, y, w, h = rect

            # Create small patch buffer for this item
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

            # Draw onto local patch
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

            # Simple approach: anywhere B+G+R > 0, set alpha to 255
            mask = np.any(patch_data[:, :, :3] > 0, axis=2)
            patch_data[mask, 3] = 255

            new_patches.append(ImagePatch(x=x, y=y, width=w, height=h, data=patch_data))

        return new_patches

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.menu_timestamp
