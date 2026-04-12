import numpy as np
from light_map.rendering.layers.visibility_layer import VisibilityLayer
from light_map.state.world_state import WorldState


def test_visibility_layer_initialization():
    ws = WorldState()
    layer = VisibilityLayer(ws, 100, 100)
    assert layer.width == 100
    assert layer.height == 100
    assert layer.get_current_version() > 0


def test_visibility_layer_render():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10)

    # Initially no mask
    assert len(layer.render()[0]) == 0

    # Set mask in state
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0, 0] = 255
    ws.update_visibility_mask(mask)

    # Set grid metadata so transformation works
    from light_map.core.common_types import GridMetadata

    ws.grid_metadata = GridMetadata(spacing_svg=16.0)

    patches = layer.render()[0]
    assert len(patches) == 1
    p = patches[0]

    # Check color at (0,0) - should be fully transparent (Visible LOS)
    assert np.array_equal(p.data[0, 0], [0, 0, 0, 0])

    # Check color at (1,1) - should be 60% opaque black (The Shroud)
    # VISIBILITY_SHROUD_ALPHA is 150 (approx 60% of 255)
    assert p.data[1, 1, 3] == 150


def test_visibility_layer_caching():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10)

    mask = np.zeros((10, 10), dtype=np.uint8)
    ws.update_visibility_mask(mask)

    # 1. First render
    p1 = layer.render()[0]
    p2 = layer.render()[0]
    assert p1 is p2

    # 2. Update mask with same data
    ws.update_visibility_mask(mask)
    p3 = layer.render()[0]
    assert (
        p3 is p1
    )  # Manager/State handles change detection, timestamp shouldn't increment

    # 3. Update with different data
    mask_new = mask.copy()
    mask_new[0, 0] = 255
    ws.update_visibility_mask(mask_new)
    p4 = layer.render()[0]
    assert p4 is not p1
