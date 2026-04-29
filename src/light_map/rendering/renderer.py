from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from light_map.core.analytics import LatencyInstrument, track_wait
from light_map.core.common_types import AppConfig, Layer


if TYPE_CHECKING:
    from light_map.rendering.projection import Projector3DModel


from light_map.rendering.composition_utils import composite_patch


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
        self._last_layer_stack: list[Layer] = []

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
        layers: list[Layer],
        current_time: float = 0.0,
        instrument: LatencyInstrument | None = None,
    ) -> np.ndarray | None:
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
        for _i, layer in enumerate(layers):
            layer_name = layer.__class__.__name__
            with track_wait(f"layer_render_{layer_name}", instrument):
                layer_patches, layer_version = layer.render(current_time)
                self.last_layer_versions[layer] = layer_version

            with track_wait(f"layer_composite_{layer_name}", instrument):
                if layer_patches:
                    for patch in layer_patches:
                        composite_patch(
                            self.output_buffer,
                            patch,
                            layer.layer_mode,
                            self.screen_width,
                            self.screen_height,
                        )

        return self.output_buffer
