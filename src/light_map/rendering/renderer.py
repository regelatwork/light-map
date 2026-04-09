import logging
from typing import Any, List, Optional, TYPE_CHECKING

import numpy as np

from light_map.core.common_types import ImagePatch, Layer, LayerMode, AppConfig
from light_map.core.analytics import LatencyInstrument, track_wait
from light_map.core.constants import ALPHA_OPAQUE

if TYPE_CHECKING:
    from light_map.rendering.projection import Projector3DModel


class Renderer:
    """
    Coordinates the compositing of multiple visual layers into a final frame.
    Optimized with intermediate caching for static layers.
    """

    def __init__(
        self,
        config: "AppConfig",
        projector_3d_model: Optional["Projector3DModel"] = None,
    ):
        self.config = config
        self.projector_3d_model = projector_3d_model

        # Main output buffer (BGR)
        self.output_buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Version tracking: Dict[Layer, int]
        self.last_layer_versions = {}
        self._last_layer_stack: List[Layer] = []

    @property
    def width(self) -> int:
        return self.config.width

    @property
    def height(self) -> int:
        return self.config.height

    @property
    def screen_width(self) -> int:
        return self.width

    @property
    def screen_height(self) -> int:
        return self.height

    def render(
        self,
        state: Any,
        layers: List[Layer],
        current_time: float = 0.0,
        instrument: Optional[LatencyInstrument] = None,
    ) -> Optional[np.ndarray]:
        """
        Composites all provided layers into the final output buffer.
        Returns None if no layers requested a new render and compositing was skipped.

        Args:
            state: The current WorldState (optional, layers use their own injected state).
            layers: A list of Layer objects, from bottom to top.
            current_time: The current application time (monotonic).
            instrument: Optional LatencyInstrument to track per-layer timings.
        """
        # 1. Check if stack changed
        stack_changed = layers != self._last_layer_stack
        if stack_changed:
            self._last_layer_stack = list(layers)

        should_composite_frame = stack_changed

        # Check for any version changes
        for layer in layers:
            layer_version = layer.get_current_version()
            if layer_version != self.last_layer_versions.get(layer, -1):
                should_composite_frame = True

        if not should_composite_frame:
            return None

        # 2. Composite All Layers
        self.output_buffer.fill(0)
        for i, layer in enumerate(layers):
            layer_name = layer.__class__.__name__
            with track_wait(f"layer_render_{layer_name}", instrument):
                layer_patches, layer_version = layer.render(current_time)
                self.last_layer_versions[layer] = layer_version

            with track_wait(f"layer_composite_{layer_name}", instrument):
                if layer_patches:
                    for patch in layer_patches:
                        self._composite_patch(
                            self.output_buffer, patch, layer.layer_mode
                        )

        return self.output_buffer

    def _composite_patch(self, buffer: np.ndarray, patch: ImagePatch, mode: LayerMode):
        """Internal helper to blend a patch onto a buffer."""
        # Bound checks
        buffer_x1, buffer_y1 = max(0, patch.x), max(0, patch.y)
        buffer_x2, buffer_y2 = (
            min(self.screen_width, patch.x + patch.width),
            min(self.screen_height, patch.y + patch.height),
        )

        if buffer_x1 >= buffer_x2 or buffer_y1 >= buffer_y2:
            return

        # Slice patch data if it's partially off-screen
        patch_x1, patch_y1 = buffer_x1 - patch.x, buffer_y1 - patch.y
        patch_x2, patch_y2 = (
            patch_x1 + (buffer_x2 - buffer_x1),
            patch_y1 + (buffer_y2 - buffer_y1),
        )
        patch_slice = patch.data[patch_y1:patch_y2, patch_x1:patch_x2]

        if mode == LayerMode.BLOCKING:
            # Fast slice assignment (ignore alpha)
            buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2] = patch_slice[:, :, :3]
        else:
            # NORMAL mode: Alpha blending
            # OPTIMIZATION: Check if patch is mostly transparent
            # If patch has an alpha channel, use it.
            if patch_slice.shape[2] == 4:
                alpha_channel = patch_slice[:, :, 3]

                # If all pixels are transparent, skip
                if not np.any(alpha_channel):
                    return

                # Standard Alpha blending: (Patch * Alpha) + (Buffer * (ALPHA_OPAQUE - Alpha)) / ALPHA_OPAQUE
                # Using uint16 to avoid overflow (255 * 255 = 65025 < 65535)
                # and then back to uint8
                alpha = alpha_channel[:, :, np.newaxis].astype(np.uint16)
                roi = buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2].astype(np.uint16)
                patch_bgr = patch_slice[:, :, :3].astype(np.uint16)

                if np.mean(alpha_channel) > 200:
                    logging.debug(
                        f"Renderer: Compositing highly opaque patch at ({buffer_x1}, {buffer_y1}) size {buffer_x2 - buffer_x1}x{buffer_y2 - buffer_y1}. Mode: {mode}"
                    )

                # Integer blending formula: (src * alpha + dst * (ALPHA_OPAQUE - alpha)) // ALPHA_OPAQUE

                blended = (
                    patch_bgr * alpha + roi * (ALPHA_OPAQUE - alpha)
                ) // ALPHA_OPAQUE
                buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2] = blended.astype(
                    np.uint8
                )
            else:
                # No alpha channel, treat as blocking
                buffer[buffer_y1:buffer_y2, buffer_x1:buffer_x2] = patch_slice[:, :, :3]
