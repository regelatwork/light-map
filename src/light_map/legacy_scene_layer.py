from typing import List, Any
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState


class LegacySceneLayer(Layer):
    """
    Wraps a legacy Scene's render method into the layered system.
    Handles the 'black is transparent' heuristic for legacy overlay scenes.
    """

    def __init__(
        self,
        state: WorldState,
        scene: Any,
        width: int,
        height: int,
        is_static: bool = True,
    ):
        super().__init__(state=state, is_static=is_static, layer_mode=LayerMode.NORMAL)
        self.scene = scene
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return self.state.scene_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.scene:
            return []

        # Provide a blank BGR buffer to the scene (Legacy bridge)
        buffer_bgr = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Scene modifies the buffer
        render_result = self.scene.render(buffer_bgr)

        # Handle modern scenes that might return (result, version)
        if isinstance(render_result, tuple):
            result_bgr = render_result[0]
        else:
            result_bgr = render_result

        # Convert to BGRA for the layered system
        result_bgra = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        result_bgra[:, :, :3] = result_bgr

        # Use alpha=255 for all pixels if scene is blocking (background is part of the scene)
        # Otherwise, use 'black is transparent' heuristic for legacy overlay scenes.
        if getattr(self.scene, "blocking", False):
            result_bgra[:, :, 3] = 255
        else:
            mask = np.any(result_bgr > 0, axis=2)
            result_bgra[mask, 3] = 255

        patch = ImagePatch(
            x=0, y=0, width=self.width, height=self.height, data=result_bgra
        )

        return [patch]
