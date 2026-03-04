import os
import cv2
import numpy as np
import logging
from typing import List, Optional
from .common_types import Layer, ImagePatch


class FogOfWarLayer(Layer):
    """
    Manages the persistent Fog of War (exploration) state.
    Renders a 3-state mask:
    1. Visible (LOS): Fully transparent.
    2. Explored: Dimmed (e.g. 70% opaque black).
    3. Unexplored: Opaque black.
    """

    def __init__(
        self, mask_width: int, mask_height: int, file_path: Optional[str] = None
    ):
        super().__init__()
        self.mask_width = mask_width
        self.mask_height = mask_height
        self.file_path = file_path
        self._is_dirty = True

        # Persistent mask (255 = explored, 0 = unexplored)
        self.explored_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)

        # Current LOS mask (255 = visible, 0 = hidden)
        self.visible_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)

        # GM Override: If True, everything is visible
        self.is_disabled = False

        if file_path:
            self.load(file_path)

    def load(self, file_path: str):
        """Loads the explored mask from a PNG file with resilience."""
        self.file_path = file_path
        if not os.path.exists(file_path):
            logging.info("FoW file not found, starting fresh: %s", file_path)
            return

        try:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                if img.shape == (self.mask_height, self.mask_width):
                    self.explored_mask = img
                    self.is_dirty = True
                else:
                    logging.warning("FoW dimension mismatch, ignoring: %s", file_path)
            else:
                logging.error("Failed to decode FoW PNG: %s", file_path)
        except Exception as e:
            logging.error("Error loading FoW: %s", e)

    def save(self, file_path: Optional[str] = None):
        """Saves the explored mask to a PNG file."""
        target = file_path or self.file_path
        if not target:
            return

        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            cv2.imwrite(target, self.explored_mask)
        except Exception as e:
            logging.error("Error saving FoW: %s", e)

    def reveal_area(self, mask: np.ndarray):
        """Unions the provided mask into the explored state."""
        if mask.shape != self.explored_mask.shape:
            # Resize if needed (e.g. different resolution)
            mask = cv2.resize(
                mask,
                (self.mask_width, self.mask_height),
                interpolation=cv2.INTER_NEAREST,
            )

        cv2.bitwise_or(self.explored_mask, mask, self.explored_mask)
        self.is_dirty = True

    def set_visible_mask(self, mask: np.ndarray):
        """Updates the current LOS mask for rendering."""
        if mask.shape != self.visible_mask.shape:
            mask = cv2.resize(
                mask,
                (self.mask_width, self.mask_height),
                interpolation=cv2.INTER_NEAREST,
            )
        self.visible_mask = mask
        self.is_dirty = True

    def reset(self):
        """Clears all exploration."""
        self.explored_mask.fill(0)
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
        fow_bgr = np.zeros((self.mask_height, self.mask_width, 3), dtype=np.uint8)

        # Calculate Alpha mask:
        # 1. Start with 255 (Unexplored = Opaque Black)
        alpha = np.full((self.mask_height, self.mask_width), 255, dtype=np.uint8)

        if self.is_disabled:
            # GM Override: Fully transparent
            alpha.fill(0)
        else:
            # 2. Explored areas are 70% opaque (Alpha 178)
            # If explored_mask == 255, alpha = 178
            alpha[self.explored_mask == 255] = 178

            # 3. Currently visible areas are 0% opaque (Alpha 0)
            # If visible_mask == 255, alpha = 0
            alpha[self.visible_mask == 255] = 0

        # Combine BGR and Alpha
        fow_bgra = cv2.merge(
            [fow_bgr[:, :, 0], fow_bgr[:, :, 1], fow_bgr[:, :, 2], alpha]
        )

        self._is_dirty = False
        return [
            ImagePatch(
                x=0, y=0, width=self.mask_width, height=self.mask_height, data=fow_bgra
            )
        ]
