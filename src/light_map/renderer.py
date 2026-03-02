from typing import List, Any, Optional
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch


class Renderer:
    """
    Coordinates the compositing of multiple visual layers into a final frame.
    """

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.output_buffer = np.zeros(
            (self.screen_height, self.screen_width, 3), dtype=np.uint8
        )
        self._force_render = True

    def render(self, state: Any, layers: List[Layer]) -> Optional[np.ndarray]:
        """
        Composites all provided layers into the final output buffer.
        Returns None if no layers requested a new render and compositing was skipped.

        Args:
            state: The current WorldState.
            layers: A list of Layer objects, from bottom to top.
        """
        layer_updated = self._force_render

        # Track timestamps before render to see if any layer generates new output
        prev_timestamps = [layer.last_rendered_timestamp for layer in layers]

        patches_to_render = []
        for i, layer in enumerate(layers):
            patches = layer.render(state)
            if not patches:
                continue

            patches_to_render.append((patches, layer.layer_mode))

            # If the layer's timestamp increased, it performed a new render
            if layer.last_rendered_timestamp > prev_timestamps[i]:
                layer_updated = True

        if not layer_updated:
            return None

        # Clear buffer (or we could rely on a BLOCKING background layer at the bottom)
        self.output_buffer.fill(0)

        for patches, mode in patches_to_render:
            for patch in patches:
                self._composite_patch(patch, mode)

        self._force_render = False
        return self.output_buffer

    def _composite_patch(self, patch: ImagePatch, mode: LayerMode):
        """Internal helper to blend a patch onto the output buffer."""
        # Bound checks
        x1, y1 = max(0, patch.x), max(0, patch.y)
        x2, y2 = (
            min(self.screen_width, patch.x + patch.width),
            min(self.screen_height, patch.y + patch.height),
        )

        if x1 >= x2 or y1 >= y2:
            return

        # Slice patch data if it's partially off-screen
        # (Assuming patch.data matches patch.width/height)
        px1, py1 = x1 - patch.x, y1 - patch.y
        px2, py2 = px1 + (x2 - x1), py1 + (y2 - y1)
        patch_slice = patch.data[py1:py2, px1:px2]

        if mode == LayerMode.BLOCKING:
            # Fast slice assignment (ignore alpha)
            self.output_buffer[y1:y2, x1:x2] = patch_slice[:, :, :3]
        else:
            # NORMAL mode: Alpha blending
            # Final = (Patch * Alpha) + (Buffer * (1 - Alpha))
            alpha = patch_slice[:, :, 3:4] / 255.0
            roi = self.output_buffer[y1:y2, x1:x2]
            blended = (patch_slice[:, :, :3] * alpha + roi * (1.0 - alpha)).astype(
                np.uint8
            )
            self.output_buffer[y1:y2, x1:x2] = blended
