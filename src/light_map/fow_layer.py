import cv2
import numpy as np
from typing import List
from .common_types import Layer, ImagePatch
from .fow_manager import FogOfWarManager


class FogOfWarLayer(Layer):
    """
    Renders the Fog of War (exploration) state from a FogOfWarManager.
    Renders a 3-state mask:
    1. Visible (LOS): Fully transparent.
    2. Explored: Dimmed (e.g. 70% opaque black).
    3. Unexplored: Opaque black.
    """

    def __init__(self, manager: FogOfWarManager):
        super().__init__()
        self.manager = manager
        self._is_dirty = True

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool):
        self._is_dirty = value

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        """
        Produces a 4-channel (BGRA) mask patch.
        Alpha channel represents the FoW state.
        """
        # Create a black BGR image
        fow_bgr = np.zeros((self.manager.height, self.manager.width, 3), dtype=np.uint8)

        # Calculate Alpha mask:
        # 1. Start with 255 (Unexplored = Opaque Black)
        alpha = np.full((self.manager.height, self.manager.width), 255, dtype=np.uint8)

        if self.manager.is_disabled:
            # GM Override: Fully transparent
            alpha.fill(0)
        else:
            # 2. Explored areas are 70% opaque (Alpha 178)
            # If explored_mask == 255, alpha = 178
            alpha[self.manager.explored_mask == 255] = 178

            # 3. Currently visible areas are 0% opaque (Alpha 0)
            # If visible_mask == 255, alpha = 0
            alpha[self.manager.visible_mask == 255] = 0

        # Combine BGR and Alpha
        fow_bgra = cv2.merge(
            [fow_bgr[:, :, 0], fow_bgr[:, :, 1], fow_bgr[:, :, 2], alpha]
        )

        self._is_dirty = False
        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.manager.width,
                height=self.manager.height,
                data=fow_bgra,
            )
        ]
