from typing import List, Any, Optional
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch


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

    def render(self, state: Any, layers: List[Layer]) -> Optional[np.ndarray]:
        """
        Composites all provided layers into the final output buffer.
        Returns None if no layers requested a new render and compositing was skipped.

        Args:
            state: The current WorldState (optional, layers use their own injected state).
            layers: A list of Layer objects, from bottom to top.
        """
        any_dirty = self._force_render
        static_dirty = self._background_dirty

        # Poll all layers for dirty status
        layer_info = []
        for layer in layers:
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
                    patches = layer.render()
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
                patches = layer.render()
                for patch in patches:
                    self._composite_patch(self.output_buffer, patch, layer.layer_mode)

        self._force_render = False
        return self.output_buffer

    def _composite_patch(
        self, buffer: np.ndarray, patch: ImagePatch, mode: LayerMode
    ):
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
            # Final = (Patch * Alpha) + (Buffer * (1 - Alpha))
            alpha = patch_slice[:, :, 3:4] / 255.0
            roi = buffer[y1:y2, x1:x2]
            blended = (patch_slice[:, :, :3] * alpha + roi * (1.0 - alpha)).astype(
                np.uint8
            )
            buffer[y1:y2, x1:x2] = blended
