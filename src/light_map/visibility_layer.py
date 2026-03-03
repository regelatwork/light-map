import cv2
import numpy as np
from typing import List, Optional
from .common_types import Layer, ImagePatch


class VisibilityLayer(Layer):
    """
    Renders the current aggregated Line-of-Sight (LOS) for all PC tokens.
    Can be used for visual effects (glow, borders) or just for standard visibility.
    In the current design, FogOfWarLayer already handles the mask, so this
    layer is optional but useful for 'Exclusive Vision' mode.
    """

    def __init__(self, mask_width: int, mask_height: int):
        super().__init__()
        self.mask_width = mask_width
        self.mask_height = mask_height
        self.visible_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
        self._is_dirty = True

    def set_mask(self, mask: np.ndarray):
        """Updates the current visibility mask."""
        if mask.shape != self.visible_mask.shape:
            mask = cv2.resize(mask, (self.mask_width, self.mask_height), interpolation=cv2.INTER_NEAREST)
        self.visible_mask = mask
        self._is_dirty = True

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool):
        self._is_dirty = value

    def _generate_patches(self) -> List[ImagePatch]:
        """
        Produces a 4-channel (BGRA) mask patch for the visible area.
        For standard visibility, this could be empty if FoWLayer handles it.
        But for 'Exclusive' mode, we might want to show a slight highlight.
        """
        # For now, let's make it an additive glow or just a highlight.
        # But per Task 5 design, it's used for the exclusive view.
        
        # Create a light blue highlight for visible areas (optional effect)
        # BGR: (255, 100, 100) with 20% alpha
        highlight = np.zeros((self.mask_height, self.mask_width, 3), dtype=np.uint8)
        highlight[self.visible_mask == 255] = [255, 100, 100]
        
        alpha = np.zeros((self.mask_height, self.mask_width), dtype=np.uint8)
        alpha[self.visible_mask == 255] = 50 # 20% opaque
        
        bgra = cv2.merge([highlight[:,:,0], highlight[:,:,1], highlight[:,:,2], alpha])
        
        self._is_dirty = False
        return [ImagePatch(x=0, y=0, width=self.mask_width, height=self.mask_height, data=bgra)]
