import numpy as np
from light_map.state.world_state import WorldState
from light_map.rendering.layers.map_grid_layer import MapGridLayer
from light_map.core.common_types import ViewportState

def test_map_grid_layer_basic_rendering():
    """Verifies that MapGridLayer produces a full-screen patch with grid crosses."""
    state = WorldState()
    width, height = 1000, 750
    layer = MapGridLayer(state, width, height)
    
    # Set grid metadata
    state.grid_spacing_svg = 100.0
    state.grid_origin_svg_x = 500.0
    state.grid_origin_svg_y = 375.0
    state.viewport = ViewportState(x=0, y=0, zoom=1.0)
    
    # Render
    patches, version = layer.render(current_time=1.0)
    
    assert len(patches) == 1
    patch = patches[0]
    assert patch.width == width
    assert patch.height == height
    assert patch.data.shape == (height, width, 4)
    
    # Check that it's not empty (should have green pixels)
    # Green is (0, 255, 0) in BGR, so index 1 in BGRA
    assert np.any(patch.data[:, :, 1] == 255)

def test_map_grid_layer_versioning():
    """Verifies that MapGridLayer updates its version when grid metadata or viewport changes."""
    state = WorldState()
    layer = MapGridLayer(state, 1000, 750)
    
    v1 = layer.get_current_version()
    
    # Change grid metadata
    state.grid_spacing_svg = 150.0
    v2 = layer.get_current_version()
    assert v2 > v1
    
    # Change viewport
    state.viewport = ViewportState(x=10, y=10)
    v3 = layer.get_current_version()
    assert v3 > v2

def test_map_grid_layer_rotation():
    """Verifies that MapGridLayer can render with rotation without crashing."""
    state = WorldState()
    width, height = 1000, 750
    layer = MapGridLayer(state, width, height)
    
    state.grid_spacing_svg = 100.0
    state.viewport = ViewportState(x=0, y=0, zoom=1.0, rotation=45.0)
    
    patches, _ = layer.render()
    assert len(patches) == 1
