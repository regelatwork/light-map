import cv2
import numpy as np
import math
import svgelements
from typing import List, Tuple
from light_map.core.common_types import Layer, ImagePatch
from light_map.state.world_state import WorldState
from light_map.core.constants import (
    VISIBILITY_SHROUD_ALPHA,
    ALPHA_OPAQUE,
    ALPHA_TRANSPARENT,
    GRID_MASK_PPI,
)


class VisibilityBaseLayer(Layer):
    """
    Base class for layers that render vision masks (Line-of-Sight).
    Handles the transformation from 'Mask Space' to 'Screen Space'.
    """

    def __init__(
        self,
        state: WorldState,
        mask_width: int,
        mask_height: int,
        grid_spacing_svg: float,
        grid_origin_svg: Tuple[float, float],
        width: int,
        height: int,
    ):
        super().__init__(state=state, is_static=True)
        self.mask_width = mask_width
        self.mask_height = mask_height
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin_svg = grid_origin_svg
        self.width = width  # Screen width
        self.height = height  # Screen height

    def _render_mask_to_patches(
        self,
        mask: np.ndarray,
        shroud_alpha: int = VISIBILITY_SHROUD_ALPHA,
        background_alpha: int = 0,
    ) -> List[ImagePatch]:
        """Core logic to transform a vision mask to screen space patches."""
        if mask.shape[0] != self.mask_height or mask.shape[1] != self.mask_width:
            import logging

            logging.error(
                f"{self.__class__.__name__}: Shape mismatch. Mask is {mask.shape}, Layer expects ({self.mask_height}, {self.mask_width})"
            )
            return []

        # 1. Create shroud in "Mask Space"
        bgra_full = np.zeros((self.mask_height, self.mask_width, 4), dtype=np.uint8)
        bgra_full[:, :, 3] = shroud_alpha

        # Punch a hole for currently visible vision (Transparent)
        bgra_full[mask == ALPHA_OPAQUE, 3] = ALPHA_TRANSPARENT

        # 2. Transform to Screen Space
        if self.state.viewport:
            vp = self.state.viewport
            cx, cy = self.width / 2, self.height / 2

            m_fow_to_svg = svgelements.Matrix()
            m_fow_to_svg.post_scale(
                self.grid_spacing_svg / GRID_MASK_PPI,
                self.grid_spacing_svg / GRID_MASK_PPI,
            )

            m_svg_to_screen = svgelements.Matrix()
            m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
            m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
            m_svg_to_screen.post_translate(vp.x, vp.y)

            final_m = m_fow_to_svg * m_svg_to_screen

            M = np.float32(
                [[final_m.a, final_m.c, final_m.e], [final_m.b, final_m.d, final_m.f]]
            )

            bgra_screen = cv2.warpAffine(
                bgra_full,
                M,
                (self.width, self.height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, background_alpha),
            )
        else:
            bgra_screen = cv2.resize(
                bgra_full, (self.width, self.height), interpolation=cv2.INTER_NEAREST
            )

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=bgra_screen,
            )
        ]
