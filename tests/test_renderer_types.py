from light_map.common_types import Layer, ImagePatch
from light_map.core.world_state import WorldState
from typing import List
import numpy as np


class MockLayer(Layer):
    def __init__(self, state: WorldState, is_static: bool = False):
        super().__init__(state=state, is_static=is_static)
        self.generate_count = 0

    def get_current_version(self) -> int:
        # For testing, version is map_version
        return self.state.map_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        self.generate_count += 1
        return [
            ImagePatch(
                x=0,
                y=0,
                width=10,
                height=10,
                data=np.zeros((10, 10, 4), dtype=np.uint8),
            )
        ]


def test_layer_caching():
    state = WorldState()
    layer = MockLayer(state)

    # First render
    patches = layer.render()[0]
    assert layer.generate_count == 1
    assert len(patches) == 1

    # Second render without change
    patches = layer.render()[0]
    assert layer.generate_count == 1

    # Change state
    from light_map.common_types import MapRenderState
    state.map_render_state = MapRenderState(opacity=0.5)
    patches = layer.render()[0]
    assert layer.generate_count == 2
