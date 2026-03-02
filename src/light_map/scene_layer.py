from typing import List, Optional, Any
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState


class SceneLayer(Layer):
    """
    Wraps a legacy Scene's render method into the layered system.
    This acts as a bridge during the transition.
    """

    def __init__(self, scene: Any, width: int, height: int):
        super().__init__(layer_mode=LayerMode.NORMAL)
        self.scene = scene
        self.width = width
        self.height = height

        # Cache
        self._cached_patch: Optional[ImagePatch] = None

    def render(self, state: WorldState) -> List[ImagePatch]:
        if not self.scene:
            return []

        # Granular Cache Check
        if state.scene_timestamp <= self.last_rendered_timestamp and self._cached_patch:
            return [self._cached_patch]

        # Provide a blank BGR buffer to the scene
        # Legacy scenes currently expect BGR
        buffer_bgr = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Scene modifies the buffer
        result_bgr = self.scene.render(buffer_bgr)

        # Convert to BGRA for the layered system
        # Heuristic for alpha: if it's not black, it's opaque.
        # This allows scenes to overlay on top of layers below.
        result_bgra = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        result_bgra[:, :, :3] = result_bgr

        mask = np.any(result_bgr > 0, axis=2)
        result_bgra[mask, 3] = 255
        self._cached_patch = ImagePatch(
            x=0, y=0, width=self.width, height=self.height, data=result_bgra
        )
        self.last_rendered_timestamp = state.scene_timestamp

        return [self._cached_patch]
