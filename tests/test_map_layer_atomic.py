from dataclasses import replace
import numpy as np
from unittest.mock import MagicMock
from light_map.core.world_state import WorldState
from light_map.map_layer import MapLayer

def test_map_layer_uses_atomic_timestamps():
    state = WorldState()
    mock_map_system = MagicMock()
    mock_map_system.is_map_loaded.return_value = True
    
    layer = MapLayer(state, mock_map_system, 800, 600)
    
    # Layer version should include viewport and map timestamps
    v1 = layer.get_current_version()
    
    # Update viewport with same value should not increment version
    state.update_viewport(state.viewport) 
    assert layer.get_current_version() == v1
    
    # Update map should increment version
    v2 = layer.get_current_version()
    state.map_version += 1
    assert layer.get_current_version() > v2
    
    # Update opacity should increment version
    v3 = layer.get_current_version()
    layer.opacity = 0.5
    assert layer.get_current_version() > v3
