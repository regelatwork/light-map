import cv2
import numpy as np
import math
import svgelements
from typing import List
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
        width: int,
        height: int,
    ):
        super().__init__(state=state, is_static=True)
        self.width = width  # Screen width
        self.height = height  # Screen height

    def _render_mask_to_patches(
        self,
        mask: np.ndarray,
        shroud_alpha: int = VISIBILITY_SHROUD_ALPHA,
        background_alpha: int = 0,
    ) -> List[ImagePatch]:
        """Core logic to transform a vision mask to screen space patches."""
        mask_h, mask_w = mask.shape[:2]

        # 1. Prepare a 1-channel mask for warping
        # Value 255: Visible (Transparent)
        # Value 127: Shroud (Dimmed)
        # Value 0 (Border): Background
        render_mask = np.full((mask_h, mask_w), 127, dtype=np.uint8)
        render_mask[mask == ALPHA_OPAQUE] = 255

        # 2. Transform to Screen Space
        if self.state.viewport:
            vp = self.state.viewport
            grid = self.state.grid_metadata
            cx, cy = self.width / 2, self.height / 2

            m_fow_to_svg = svgelements.Matrix()
            m_fow_to_svg.post_scale(
                grid.spacing_svg / GRID_MASK_PPI,
                grid.spacing_svg / GRID_MASK_PPI,
            )

            m_svg_to_screen = svgelements.Matrix()
            m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
            m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
            m_svg_to_screen.post_translate(vp.x, vp.y)

            final_m = m_fow_to_svg * m_svg_to_screen

            M = np.float32(
                [[final_m.a, final_m.c, final_m.e], [final_m.b, final_m.d, final_m.f]]
            )

            mask_screen = cv2.warpAffine(
                render_mask,
                M,
                (self.width, self.height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            )
        else:
            mask_screen = cv2.resize(
                render_mask, (self.width, self.height), interpolation=cv2.INTER_NEAREST
            )

        # 3. Construct BGRA output in screen space using LUT for alpha mapping
        # lut maps: 0 -> background_alpha, 127 -> shroud_alpha, 255 -> ALPHA_TRANSPARENT
        lut = np.zeros(256, dtype=np.uint8)
        lut[0] = background_alpha
        lut[127] = shroud_alpha
        lut[255] = ALPHA_TRANSPARENT

        alpha_screen = cv2.LUT(mask_screen, lut)

        # Create final BGRA image (all zeros except alpha)
        bgra_screen = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        bgra_screen[:, :, 3] = alpha_screen

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=bgra_screen,
            )
        ]
