import math

import cv2
import numpy as np
import svgelements

from light_map.core.common_types import ImagePatch, Layer, LayerMode
from light_map.core.constants import ALPHA_OPAQUE, ALPHA_TRANSPARENT, GRID_MASK_PPI
from light_map.state.world_state import WorldState


class FogOfWarLayer(Layer):
    """
    Renders the Fog of War (exploration) state from the WorldState.
    Renders a 3-state mask:
    1. Visible (LOS): Fully transparent.
    2. Explored: Dimmed (e.g. 70% opaque black).
    3. Unexplored: Opaque black.

    Correctly transforms the mask from grid-space to screen-space based on the viewport.
    """

    def __init__(
        self,
        state: WorldState,
        width: int,
        height: int,
    ):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.MASKED)
        self.width = width  # Screen width
        self.height = height  # Screen height

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(
            self.state.fow_version,
            self.state.fow_disabled_version,
            self.state.viewport_version,
            self.state.visibility_version,
            self.state.grid_metadata_version,
        )

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        """
        Produces a 4-channel (BGRA) mask patch covering the full screen.
        """
        if self.state is None or self.state.fow_disabled or self.state.fow_mask is None:
            # GM Override or no mask: No patches to render
            return []

        fow_mask = self.state.fow_mask
        mask_h, mask_w = fow_mask.shape[:2]

        # 1. Create the full map FoW mask in "Mask Space"
        # Create a black BGR image
        fow_bgr_full = np.zeros((mask_h, mask_w, 3), dtype=np.uint8)

        # Calculate Alpha mask:
        # 1. Start with ALPHA_OPAQUE (Unexplored = Opaque Black)
        alpha_full = np.full((mask_h, mask_w), ALPHA_OPAQUE, dtype=np.uint8)

        # 2. Explored areas are 0% opaque (Alpha 0) - They are fully revealed by THIS layer
        alpha_full[fow_mask == ALPHA_OPAQUE] = ALPHA_TRANSPARENT

        # Combine BGR and Alpha for the full mask
        fow_bgra_full = cv2.merge(
            [
                fow_bgr_full[:, :, 0],
                fow_bgr_full[:, :, 1],
                fow_bgr_full[:, :, 2],
                alpha_full,
            ]
        )

        # 2. Transform the full mask to Screen Space
        if self.state and self.state.viewport:
            vp = self.state.viewport
            grid = self.state.grid_metadata
            cx, cy = self.width / 2, self.height / 2

            # M_fow_to_svg:
            # Scale by grid_spacing_svg / GRID_MASK_PPI
            # Mask (0,0) now corresponds to SVG (0,0)
            m_fow_to_svg = svgelements.Matrix()
            m_fow_to_svg.post_scale(
                grid.spacing_svg / GRID_MASK_PPI,
                grid.spacing_svg / GRID_MASK_PPI,
            )

            # M_svg_to_screen:
            m_svg_to_screen = svgelements.Matrix()
            m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
            m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
            m_svg_to_screen.post_translate(vp.x, vp.y)

            # Combined: Screen = M_svg_to_screen * M_fow_to_svg * FoW_Point
            final_m = m_fow_to_svg * m_svg_to_screen

            # Extract 2x3 Affine Matrix for OpenCV
            M = np.float32(
                [
                    [final_m.a, final_m.c, final_m.e],
                    [final_m.b, final_m.d, final_m.f],
                ]
            )

            # Warp the full mask to screen dimensions
            # Use INTER_NEAREST for the mask to avoid interpolation artifacts on the alpha states
            fow_bgra_screen = cv2.warpAffine(
                fow_bgra_full,
                M,
                (self.width, self.height),
                flags=cv2.INTER_NEAREST,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, ALPHA_OPAQUE),  # Opaque black for out-of-bounds
            )
        else:
            # Fallback (should not happen if state is present)
            fow_bgra_screen = cv2.resize(
                fow_bgra_full,
                (self.width, self.height),
                interpolation=cv2.INTER_NEAREST,
            )

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=fow_bgra_screen,
            )
        ]
