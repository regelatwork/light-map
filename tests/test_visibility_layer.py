import numpy as np
from light_map.visibility_layer import VisibilityLayer
from light_map.core.world_state import WorldState


def test_visibility_layer_initialization():
    ws = WorldState()
    layer = VisibilityLayer(ws, 100, 100, 10.0, (0.0, 0.0), 100, 100)
    assert layer.mask_width == 100
    assert layer.mask_height == 100
    assert layer.is_dirty is True


def test_visibility_layer_render():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10, 10.0, (0.0, 0.0), 10, 10)

    # Initially no mask
    assert len(layer.render()) == 0

    # Set mask in state
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0, 0] = 255
    ws.update_visibility_mask(mask)

    patches = layer.render()
    assert len(patches) == 1
    p = patches[0]

    # Check color at (0,0) - should be light blue highlight
    # highlight[visible_mask == 255] = [255, 100, 100]
    # alpha[visible_mask == 255] = 150
    assert np.array_equal(p.data[0, 0], [255, 100, 100, 150])
    # Check outside
    assert np.array_equal(p.data[1, 1], [0, 0, 0, 0])


def test_visibility_layer_caching():
    ws = WorldState()
    layer = VisibilityLayer(ws, 10, 10, 10.0, (0.0, 0.0), 10, 10)

    mask = np.zeros((10, 10), dtype=np.uint8)
    ws.update_visibility_mask(mask)

    # 1. First render
    p1 = layer.render()
    p2 = layer.render()
    assert p1 is p2

    # 2. Update mask with same data
    ws.update_visibility_mask(mask)
    p3 = layer.render()
    assert (
        p3 is p1
    )  # Manager/State handles change detection, timestamp shouldn't increment

    # 3. Update with different data
    mask[0, 0] = 255
    ws.update_visibility_mask(mask)
    p4 = layer.render()
    assert p4 is not p1
