from typing import List, Any, Dict, Optional
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState
from .map_system import MapSystem


class MapLayer(Layer):
    """
    Renders the background SVG map from MapSystem.
    Uses timestamps for efficient caching.
    """

    def __init__(
        self, state: WorldState, map_system: MapSystem, width: int, height: int
    ):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.BLOCKING)
        self.map_system = map_system
        self.width = width
        self.height = height

        # State
        self.opacity: float = 1.0
        self.quality: float = 1.0

        # Cache Tracking
        self._last_render_params: Dict[str, Any] = {}
        self._last_opacity: float = 1.0
        self._cached_map_bgra: Optional[np.ndarray] = None

    @property
    def is_dirty(self) -> bool:
        if not self.map_system.is_map_loaded():
            return False

        if self.state is None:
            return True

        current_params = self.map_system.get_render_params().copy()
        current_params["quality"] = self.quality

        return (
            self.state.map_timestamp > self._last_state_timestamp
            or self.state.viewport_timestamp > self._last_state_timestamp
            or current_params != self._last_render_params
            or self.opacity != self._last_opacity
            or self._cached_map_bgra is None
        )

    def _generate_patches(self) -> List[ImagePatch]:
        if not self.map_system.is_map_loaded():
            return []

        # Granular Cache Check for SVG Rendering
        current_params = self.map_system.get_render_params().copy()
        current_params["quality"] = self.quality

        # Only re-render SVG if params changed or cache is empty or timestamps updated
        if (
            current_params != self._last_render_params
            or self._cached_map_bgra is None
            or self.state.map_timestamp > self._last_state_timestamp
            or self.state.viewport_timestamp > self._last_state_timestamp
        ):
            # Render from SVG
            map_bgr = self.map_system.svg_loader.render(
                self.width, self.height, **current_params
            )
            # Convert BGR to BGRA and cache the result
            self._cached_map_bgra = cv2.cvtColor(map_bgr, cv2.COLOR_BGR2BGRA)
            self._last_render_params = current_params.copy()

        # Apply Opacity (Dimming) to cached map if needed
        final_data = self._cached_map_bgra
        if self.opacity < 1.0:
            # We must copy if we modify
            final_data = self._cached_map_bgra.copy()
            # Dim BGR channels
            final_data[:, :, :3] = cv2.convertScaleAbs(
                final_data[:, :, :3], alpha=self.opacity, beta=0
            )

        patch = ImagePatch(
            x=0, y=0, width=self.width, height=self.height, data=final_data
        )

        # Update tracking
        self._last_opacity = self.opacity
        self._update_timestamp()

        return [patch]

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = max(
                self.state.map_timestamp, self.state.viewport_timestamp
            )
