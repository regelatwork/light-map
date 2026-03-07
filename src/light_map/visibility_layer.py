import cv2
import numpy as np
import math
import svgelements
from typing import List, Tuple, Optional
from .common_types import Layer, ImagePatch
from .core.world_state import WorldState


class VisibilityLayer(Layer):
    """
    Renders the current aggregated Line-of-Sight (LOS) for all PC tokens.
    Consumes mask from WorldState and transforms it to screen space.
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
        super().__init__(state=state)
        self.mask_width = mask_width
        self.mask_height = mask_height
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin_svg = grid_origin_svg
        self.width = width  # Screen width
        self.height = height  # Screen height

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True
        return (
            self.state.visibility_timestamp > self._last_state_timestamp
            or self.state.viewport_timestamp > self._last_state_timestamp
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or self.state.visibility_mask is None:
            return []

        return self._render_mask_to_patches(self.state.visibility_mask)

    def _render_mask_to_patches(self, mask: np.ndarray) -> List[ImagePatch]:
        """Core logic to transform a vision mask to screen space patches."""
        if mask.shape[0] != self.mask_height or mask.shape[1] != self.mask_width:
            import logging

            logging.error(
                f"VisibilityLayer: Shape mismatch. Mask is {mask.shape}, Layer expects ({self.mask_height}, {self.mask_width})"
            )
            return []

        # Create a light blue highlight for visible areas
        # 1. Create highlight in "Mask Space"
        highlight_full = np.zeros(
            (self.mask_height, self.mask_width, 3), dtype=np.uint8
        )
        highlight_full[mask == 255] = [255, 100, 100]

        alpha_full = np.zeros((self.mask_height, self.mask_width), dtype=np.uint8)
        alpha_full[mask == 255] = 150  # ~60% opaque

        bgra_full = cv2.merge(
            [
                highlight_full[:, :, 0],
                highlight_full[:, :, 1],
                highlight_full[:, :, 2],
                alpha_full,
            ]
        )

        # 2. Transform to Screen Space
        if self.state.viewport:
            vp = self.state.viewport
            cx, cy = self.width / 2, self.height / 2

            m_fow_to_svg = svgelements.Matrix()
            m_fow_to_svg.post_scale(
                self.grid_spacing_svg / 16.0, self.grid_spacing_svg / 16.0
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
                borderValue=(0, 0, 0, 0),
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

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = max(
                self.state.visibility_timestamp, self.state.viewport_timestamp
            )


class ExclusiveVisionLayer(VisibilityLayer):
    """
    Renders the real-time Line-of-Sight (LOS) for a single inspected token.
    Acting as a 'searchlight': it masks everything outside the vision mask with darkness.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mask_override: Optional[np.ndarray] = None

    def set_mask(self, mask: Optional[np.ndarray]):
        self.mask_override = mask

    @property
    def is_dirty(self) -> bool:
        # Since this is for real-time inspection, we consider it dirty if we have a mask.
        return self.mask_override is not None

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.mask_override is None:
            return []

        # Validate shape before rendering
        mask = self.mask_override
        if mask.shape[0] != self.mask_height or mask.shape[1] != self.mask_width:
            import logging

            logging.error(
                f"ExclusiveVisionLayer: Shape mismatch. Mask is {mask.shape}, Layer expects ({self.mask_height}, {self.mask_width})"
            )
            return []

        # Create 'Total Darkness' mask in Mask Space
        # Everything is Opaque Black (0, 0, 0, 255)
        # Except visible areas which are Transparent (0, 0, 0, 0)
        bgra_full = np.zeros((self.mask_height, self.mask_width, 4), dtype=np.uint8)
        bgra_full[:, :, 3] = 255  # Fully Opaque Black

        # Punch a hole for vision
        bgra_full[mask == 255, 3] = 0  # Fully Transparent

        # Transform to Screen Space
        if self.state.viewport:
            vp = self.state.viewport
            cx, cy = self.width / 2, self.height / 2

            m_fow_to_svg = svgelements.Matrix()
            m_fow_to_svg.post_scale(
                self.grid_spacing_svg / 16.0, self.grid_spacing_svg / 16.0
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
                borderValue=(0, 0, 0, 255),  # Darkness outside the warp
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
