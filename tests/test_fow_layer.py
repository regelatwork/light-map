import numpy as np
from light_map.fow_layer import FogOfWarLayer
from light_map.fow_manager import FogOfWarManager


from light_map.core.world_state import WorldState


def test_fow_initialization():
    ws = WorldState()
    manager = FogOfWarManager(100, 100)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 100, 100)
    assert layer.manager.width == 100
    assert layer.manager.height == 100
    assert layer.is_dirty is True


def test_fow_render_three_states():
    ws = WorldState()
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 10, 10)

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
    ws = WorldState()
    manager = FogOfWarManager(10, 10)
    layer = FogOfWarLayer(ws, manager, 10.0, (0.0, 0.0), 10, 10)
    manager.is_disabled = True
    layer.is_dirty = True

    patches = layer.render()
    # No patches should be returned when disabled
    assert len(patches) == 0
