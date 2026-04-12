import numpy as np
from typing import List
from light_map.core.common_types import Layer, LayerMode, ImagePatch
from light_map.state.world_state import WorldState


class FlashLayer(Layer):
    def __init__(self, state: WorldState, width: int, height: int):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.BLOCKING)
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        # Returns the timestamp of the calibration atom to trigger re-renders
        return self.state.calibration_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        # Use flash_intensity from the calibration state
        intensity = self.state.calibration.flash_intensity
        # Create a full-screen patch with the specified intensity (BGR)
        img = np.full((self.height, self.width, 3), intensity, dtype=np.uint8)

        # Convert to BGRA for the layered system (Opaque since it's BLOCKING)
        img_bgra = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        img_bgra[:, :, :3] = img
        img_bgra[:, :, 3] = 255

        return [ImagePatch(0, 0, self.width, self.height, img_bgra)]
