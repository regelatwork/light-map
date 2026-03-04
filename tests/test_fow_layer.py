import numpy as np
from light_map.fow_layer import FogOfWarLayer
from light_map.fow_manager import FogOfWarManager


def test_fow_initialization():
    manager = FogOfWarManager(100, 100)
    layer = FogOfWarLayer(manager)
    assert layer.manager.width == 100
    assert layer.manager.height == 100
    assert layer.is_dirty is True


def test_fow_render_three_states():
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(manager)

    # 1. Unexplored (All black/opaque)
    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert np.all(alpha == 255)

    # 2. Explored but not visible (Dimmed/70% opaque)
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[0, 0] = 255
    manager.reveal_area(explored)
    layer.is_dirty = True

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert alpha[0, 0] == 178
    assert alpha[1, 1] == 255

    # 3. Visible (Transparent)
    visible = np.zeros((10, 10), dtype=np.uint8)
    visible[0, 0] = 255
    manager.set_visible_mask(visible)
    layer.is_dirty = True

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert alpha[0, 0] == 0
    assert alpha[1, 1] == 255


def test_fow_gm_override():
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(manager)
    manager.is_disabled = True
    layer.is_dirty = True

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    # Everything should be transparent (Alpha 0)
    assert np.all(alpha == 0)
