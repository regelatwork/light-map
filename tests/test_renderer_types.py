from light_map.common_types import Layer, ImagePatch, LayerMode
from light_map.core.world_state import WorldState
from typing import List, Optional
import numpy as np
import pytest

class MockLayer(Layer):
    def __init__(self, state: WorldState, is_static: bool = False):
        super().__init__(state=state, is_static=is_static)
        self.generate_count = 0
    
    @property
    def is_dirty(self) -> bool:
        # For testing, dirty if map_timestamp changed
        return self.state.map_timestamp > self._last_state_timestamp
    
    def _generate_patches(self) -> List[ImagePatch]:
        self.generate_count += 1
        return [ImagePatch(x=0, y=0, width=10, height=10, data=np.zeros((10, 10, 4), dtype=np.uint8))]
    
    def _update_timestamp(self):
        self._last_state_timestamp = self.state.map_timestamp

def test_layer_caching():
    state = WorldState()
    layer = MockLayer(state)
    
    # First render
    patches = layer.render()
    assert layer.generate_count == 1
    assert len(patches) == 1
    
    # Second render without change
    patches = layer.render()
    assert layer.generate_count == 1
    
    # Change state
    state.increment_map_timestamp()
    patches = layer.render()
    assert layer.generate_count == 2
