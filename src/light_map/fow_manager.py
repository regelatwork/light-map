import os
import cv2
import numpy as np
import logging
from typing import Optional


class FogOfWarManager:
    """
    Manages the persistent Fog of War (exploration) state and visibility masks.
    Separates state management and persistence from rendering.
    """

    def __init__(self, width: int, height: int, file_path: Optional[str] = None):
        self.width = width
        self.height = height
        self.file_path = file_path

        # Persistent mask (255 = explored, 0 = unexplored)
        self.explored_mask = np.zeros((height, width), dtype=np.uint8)

        # Current LOS mask (255 = visible, 0 = hidden)
        self.visible_mask = np.zeros((height, width), dtype=np.uint8)

        # GM Override: If True, everything is visible
        self.is_disabled = False

        if file_path:
            self.load(file_path)

    def load(self, file_path: str):
        """Loads the explored mask from a PNG file."""
        self.file_path = file_path
        if not os.path.exists(file_path):
            logging.info("FoW file not found, starting fresh: %s", file_path)
            return

        try:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                if img.shape == (self.height, self.width):
                    self.explored_mask = img
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
