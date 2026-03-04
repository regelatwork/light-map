import cv2
import numpy as np
from typing import List
from .common_types import Layer, ImagePatch
from .core.world_state import WorldState


class VisibilityLayer(Layer):
    """
    Renders the current aggregated Line-of-Sight (LOS) for all PC tokens.
    Consumes mask from WorldState.
    """

    def __init__(self, state: WorldState, mask_width: int, mask_height: int):
        super().__init__(state=state)
        self.mask_width = mask_width
        self.mask_height = mask_height

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True
        return self.state.visibility_timestamp > self._last_state_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or self.state.visibility_mask is None:
            return []

        visible_mask = self.state.visibility_mask

        # Create a light blue highlight for visible areas (Exclusive Vision mode)
        highlight = np.zeros((self.mask_height, self.mask_width, 3), dtype=np.uint8)
        highlight[visible_mask == 255] = [255, 100, 100]

        alpha = np.zeros((self.mask_height, self.mask_width), dtype=np.uint8)
        alpha[visible_mask == 255] = 50  # 20% opaque

        bgra = cv2.merge(
            [highlight[:, :, 0], highlight[:, :, 1], highlight[:, :, 2], alpha]
        )

        return [
            ImagePatch(
                x=0, y=0, width=self.mask_width, height=self.mask_height, data=bgra
            )
        ]

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.visibility_timestamp
