from typing import Any, List, Optional

import numpy as np

from .common_types import ImagePatch, Layer, LayerMode
from .core.analytics import LatencyInstrument, track_wait


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

        self._force_render = True
        self._background_dirty = True
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
        # If the layer stack itself changed (e.g., scene switch), we MUST force a full redraw
        # and invalidate the background cache.
        stack_changed = layers != self._last_layer_stack
        if stack_changed:
            self._force_render = True
            self._background_dirty = True
            self._last_layer_stack = list(layers)

        any_dirty = self._force_render
        static_dirty = self._background_dirty

        # Poll all layers for dirty status
        layer_info = []
        for i, layer in enumerate(layers):
            is_dirty = layer.is_dirty
            layer_info.append(is_dirty)
            if is_dirty:
                any_dirty = True
                if layer.is_static:
                    static_dirty = True

        if not any_dirty:
            return None

        # 1. Update Background Cache if needed
        if static_dirty:
            self.background_cache.fill(0)
            for i, layer in enumerate(layers):
                if layer.is_static:
                    layer_name = layer.__class__.__name__
                    with track_wait(f"layer_render_{layer_name}", instrument):
                        patches = layer.render(current_time)
                    with track_wait(f"layer_composite_{layer_name}", instrument):
                        for patch in patches:
                            self._composite_patch(
                                self.background_cache, patch, layer.layer_mode
                            )
            self._background_dirty = False

        # 2. Copy Background Cache to Output Buffer
        np.copyto(self.output_buffer, self.background_cache)

        # 3. Composite Dynamic Layers
        for i, layer in enumerate(layers):
            if not layer.is_static:
                layer_name = layer.__class__.__name__
                # We only render and composite if it's dirty or we are forced
                # But Layer.render() usually handles its own internal caching/dirty check.
                # However, for consistency and clear stats, we wrap it.
                with track_wait(f"layer_render_{layer_name}", instrument):
                    patches = layer.render(current_time)
                with track_wait(f"layer_composite_{layer_name}", instrument):
                    for patch in patches:
                        self._composite_patch(
                            self.output_buffer, patch, layer.layer_mode
                        )

        self._force_render = False
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

                # If all pixels are opaque, do blocking copy
                if np.all(alpha_channel == 255):
                    buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
                    return

                # Standard Alpha blending: (Patch * Alpha) + (Buffer * (1 - Alpha))
                # Using float32 for blending to avoid overflow and then back to uint8
                alpha = alpha_channel[:, :, np.newaxis].astype(np.float32) / 255.0
                roi = buffer[y1:y2, x1:x2].astype(np.float32)
                patch_bgr = patch_slice[:, :, :3].astype(np.float32)

                blended = (patch_bgr * alpha + roi * (1.0 - alpha)).astype(np.uint8)
                buffer[y1:y2, x1:x2] = blended
            else:
                # No alpha channel, treat as blocking
                buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
