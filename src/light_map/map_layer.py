from typing import List, Optional
import cv2
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState
from .map_system import MapSystem


class MapLayer(Layer):
    """
    Renders the background SVG map from MapSystem.
    Uses timestamps for efficient caching.
    """

    def __init__(self, map_system: MapSystem, width: int, height: int):
        super().__init__(layer_mode=LayerMode.BLOCKING)
        self.map_system = map_system
        self.width = width
        self.height = height

        # State
        self.opacity: float = 1.0
        self.quality: float = 1.0

        # Cache
        self._cached_patch: Optional[ImagePatch] = None
        self._last_render_params = {}
        self._last_opacity = 1.0

    def render(self, state: WorldState) -> List[ImagePatch]:
        if not self.map_system.is_map_loaded():
            return []

        # Granular Cache Check
        current_params = self.map_system.get_render_params().copy()
        current_params["quality"] = self.quality

        # Check timestamps and params
        is_dirty = (
            state.map_timestamp > self.last_rendered_timestamp
            or state.viewport_timestamp > self.last_rendered_timestamp
            or current_params != self._last_render_params
            or self.opacity != self._last_opacity
            or self._cached_patch is None
        )

        if is_dirty:
            # Render from SVG
            map_bgr = self.map_system.svg_loader.render(
                self.width, self.height, **current_params
            )

            # Apply Opacity (Dimming)
            if self.opacity < 1.0:
                map_bgr = cv2.convertScaleAbs(map_bgr, alpha=self.opacity, beta=0)

            # Convert BGR to BGRA
            map_bgra = cv2.cvtColor(map_bgr, cv2.COLOR_BGR2BGRA)

            self._cached_patch = ImagePatch(
                x=0, y=0, width=self.width, height=self.height, data=map_bgra
            )
            self._last_render_params = current_params.copy()
            self._last_opacity = self.opacity
            # Update last_rendered_timestamp to the max of current relevant timestamps
            self.last_rendered_timestamp = max(
                state.map_timestamp, state.viewport_timestamp
            )

        return [self._cached_patch] if self._cached_patch else []
