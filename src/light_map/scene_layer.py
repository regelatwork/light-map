from typing import List, Any
from .common_types import Layer, ImagePatch
from .core.world_state import WorldState


class SceneLayer(Layer):
    """
    Renders visual output from modular Scene objects.
    Modern scenes should ideally produce ImagePatches directly or provide a
    standardized rendering interface.
    """

    def __init__(
        self,
        state: WorldState,
        scene: Any,
        width: int,
        height: int,
        is_static: bool = True,
    ):
        from .common_types import LayerMode

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

        # FOR NOW: Delegate to scene.render and wrap in patch.
        # Future modular scenes may return List[ImagePatch] directly.
        import numpy as np

        buffer_bgr = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        render_result = self.scene.render(buffer_bgr)

        # Handle modern scenes that might return (result, version)
        if isinstance(render_result, tuple):
            result_bgr = render_result[0]
        else:
            result_bgr = render_result

        result_bgra = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        result_bgra[:, :, :3] = result_bgr

        # Modular scenes are expected to manage their own background/transparency.
        # If marked as blocking, we set alpha to opaque.
        if getattr(self.scene, "blocking", False):
            result_bgra[:, :, 3] = 255
        else:
            # Still use the heuristic for now, but modular scenes should
            # ideally handle this or return BGRA directly.
            mask = np.any(result_bgr > 0, axis=2)
            result_bgra[mask, 3] = 255
            # Alpha is already 0 where not masked due to np.zeros initialization

        return [
            ImagePatch(x=0, y=0, width=self.width, height=self.height, data=result_bgra)
        ]
