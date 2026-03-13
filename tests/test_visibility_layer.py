import numpy as np
from light_map.visibility_layer import VisibilityLayer
from light_map.core.world_state import WorldState


def test_visibility_layer_initialization():
    ws = WorldState()
    layer = VisibilityLayer(ws, 100, 100, 10.0, (0.0, 0.0), 100, 100)
    assert layer.mask_width == 100
    assert layer.mask_height == 100
    assert layer.get_current_version() == 0


def test_visibility_layer_render():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10, 10.0, (0.0, 0.0), 10, 10)

    # Initially no mask
    assert len(layer.render()[0]) == 0

    # Set mask in state
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0, 0] = 255
    ws.update_visibility_mask(mask)

    patches = layer.render()[0]
    assert len(patches) == 1
    p = patches[0]

    # Check color at (0,0) - should be fully transparent (Visible LOS)
    assert np.array_equal(p.data[0, 0], [0, 0, 0, 0])

    # Check color at (1,1) - should be 60% opaque black (The Shroud)
    assert np.array_equal(p.data[1, 1], [0, 0, 0, 150])


def test_visibility_layer_caching():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10, 10.0, (0.0, 0.0), 10, 10)

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
    mask[0, 0] = 255
    ws.update_visibility_mask(mask)
    p4 = layer.render()[0]
    assert p4 is not p1
