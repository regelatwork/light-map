import numpy as np
import cv2
import logging


class FogOfWarManager:
    """
    Manages the in-memory Fog of War (exploration) state and visibility masks.
    Separates state management and logic from persistence.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

        # Persistent mask (ALPHA_OPAQUE = explored, 0 = unexplored)
        self.explored_mask = np.zeros((height, width), dtype=np.uint8)

        # Current LOS mask (ALPHA_OPAQUE = visible, 0 = hidden)
        self.visible_mask = np.zeros((height, width), dtype=np.uint8)

        # GM Override: If True, everything is visible
        self.is_disabled = False

    def sync_resolution(self, width: int, height: int):
        """Re-allocates or resizes masks if the provided dimensions have changed."""
        h, w = self.explored_mask.shape
        if w != width or h != height:
            logging.info(f"FogOfWarManager: Syncing resolution to {width}x{height}")
            self.width = width
            self.height = height
            self.explored_mask = cv2.resize(
                self.explored_mask,
                (width, height),
                interpolation=cv2.INTER_NEAREST,
            )
            self.visible_mask = cv2.resize(
                self.visible_mask,
                (width, height),
                interpolation=cv2.INTER_NEAREST,
            )

    def reveal_area(self, mask: np.ndarray):
        """Unions the provided mask into the explored state."""
        if mask.shape != self.explored_mask.shape:
            mask = cv2.resize(
                mask,
                (self.width, self.height),
                interpolation=cv2.INTER_NEAREST,
            )

        cv2.bitwise_or(self.explored_mask, mask, self.explored_mask)

    def set_visible_mask(self, mask: np.ndarray):
        """Updates the current LOS mask."""
        if mask.shape != self.visible_mask.shape:
            mask = cv2.resize(
                mask,
                (self.width, self.height),
                interpolation=cv2.INTER_NEAREST,
            )
        self.visible_mask = mask

    def reset(self):
        """Clears all exploration."""
        self.explored_mask.fill(0)
        self.visible_mask.fill(0)
