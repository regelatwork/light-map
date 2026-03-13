from typing import Any, List, Optional

import numpy as np

from .common_types import ImagePatch, Layer, LayerMode
from .core.analytics import LatencyInstrument, track_wait
from .constants import ALPHA_OPAQUE


class Renderer:
    """
    Coordinates the compositing of multiple visual layers into a final frame.
    Optimized with intermediate caching for static layers.
    """

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Main output buffer (BGR)
        self.output_buffer = np.zeros(
            (self.screen_height, self.screen_width, 3), dtype=np.uint8
        )

        # Cache for static layers (BGR)
        self.background_cache = np.zeros(
            (self.screen_height, self.screen_width, 3), dtype=np.uint8
        )

        # Version tracking: Dict[Layer, int]
        self.last_layer_versions = {}
        self._background_cache_version = -1
        self._last_layer_stack: List[Layer] = []

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
        # 1. Check if stack changed or any layer is dirty
        stack_changed = layers != self._last_layer_stack
        if stack_changed:
            self._last_layer_stack = list(layers)
            self._background_cache_version = -1  # Invalidate

        any_dirty = stack_changed
        static_dirty = (self._background_cache_version == -1)

        # Get current versions of all layers
        current_layer_versions = {}
        for layer in layers:
            v = layer.get_current_version()
            current_layer_versions[layer] = v
            
            # If dynamic or version increased, it's dirty
            if getattr(layer, "_is_dynamic", False) or v > self.last_layer_versions.get(layer, -1):
                any_dirty = True
                if layer.is_static:
                    static_dirty = True

        if not any_dirty:
            return None

        # 2. Update Background Cache if needed
        if static_dirty:
            self.background_cache.fill(0)
            for i, layer in enumerate(layers):
                if layer.is_static:
                    layer_name = layer.__class__.__name__
                    with track_wait(f"layer_render_{layer_name}", instrument):
                        patches, version = layer.render(current_time)
                        self.last_layer_versions[layer] = version

                    with track_wait(f"layer_composite_{layer_name}", instrument):
                        for patch in patches:
                            self._composite_patch(
                                self.background_cache, patch, layer.layer_mode
                            )
            self._background_cache_version = 0  # Validated static portion

        # 3. Copy Background Cache to Output Buffer
        np.copyto(self.output_buffer, self.background_cache)

        # 4. Composite Dynamic Layers
        for i, layer in enumerate(layers):
            if not layer.is_static:
                layer_name = layer.__class__.__name__
                with track_wait(f"layer_render_{layer_name}", instrument):
                    patches, version = layer.render(current_time)
                    self.last_layer_versions[layer] = version

                with track_wait(f"layer_composite_{layer_name}", instrument):
                    for patch in patches:
                        self._composite_patch(
                            self.output_buffer, patch, layer.layer_mode
                        )

        return self.output_buffer

    def _composite_patch(self, buffer: np.ndarray, patch: ImagePatch, mode: LayerMode):
        """Internal helper to blend a patch onto a buffer."""
        # Bound checks
        x1, y1 = max(0, patch.x), max(0, patch.y)
        x2, y2 = (
            min(self.screen_width, patch.x + patch.width),
            min(self.screen_height, patch.y + patch.height),
        )

        if x1 >= x2 or y1 >= y2:
            return

        # Slice patch data if it's partially off-screen
        px1, py1 = x1 - patch.x, y1 - patch.y
        px2, py2 = px1 + (x2 - x1), py1 + (y2 - y1)
        patch_slice = patch.data[py1:py2, px1:px2]

        if mode == LayerMode.BLOCKING:
            # Fast slice assignment (ignore alpha)
            buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
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
                roi = buffer[y1:y2, x1:x2].astype(np.uint16)
                patch_bgr = patch_slice[:, :, :3].astype(np.uint16)

                # Integer blending formula: (src * alpha + dst * (ALPHA_OPAQUE - alpha)) // ALPHA_OPAQUE
                blended = (
                    patch_bgr * alpha + roi * (ALPHA_OPAQUE - alpha)
                ) // ALPHA_OPAQUE
                buffer[y1:y2, x1:x2] = blended.astype(np.uint8)
            else:
                # No alpha channel, treat as blocking
                buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
