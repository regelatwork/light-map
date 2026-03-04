import numpy as np
import os
from light_map.fow_layer import FogOfWarLayer


def test_fow_initialization():
    layer = FogOfWarLayer(100, 100)
    assert layer.mask_width == 100
    assert layer.mask_height == 100
    assert np.all(layer.explored_mask == 0)
    assert np.all(layer.visible_mask == 0)


def test_fow_reveal_area():
    layer = FogOfWarLayer(100, 100)
    # Reveal a 10x10 square at (10, 10)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:20, 10:20] = 255

    layer.reveal_area(mask)
    assert np.sum(layer.explored_mask == 255) == 100
    assert layer.explored_mask[15, 15] == 255
    assert layer.explored_mask[0, 0] == 0


def test_fow_render_three_states():
    layer = FogOfWarLayer(10, 10)

    # 1. Unexplored (All black/opaque)
    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert np.all(alpha == 255)

    # 2. Explored but not visible (Dimmed/70% opaque)
    explored = np.zeros((10, 10), dtype=np.uint8)
    explored[0, 0] = 255
    layer.reveal_area(explored)

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert alpha[0, 0] == 178
    assert alpha[1, 1] == 255

    # 3. Visible (Transparent)
    visible = np.zeros((10, 10), dtype=np.uint8)
    visible[0, 0] = 255
    layer.set_visible_mask(visible)

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    assert alpha[0, 0] == 0
    assert alpha[1, 1] == 255


def test_fow_gm_override():
    layer = FogOfWarLayer(10, 10)
    layer.is_disabled = True

    patches = layer.render()
    alpha = patches[0].data[:, :, 3]
    # Everything should be transparent (Alpha 0)
    assert np.all(alpha == 0)


def test_fow_persistence(tmp_path):
    fow_path = str(tmp_path / "fow.png")
    layer = FogOfWarLayer(10, 10)
    layer.explored_mask[0, 0] = 255
    layer.save(fow_path)

    assert os.path.exists(fow_path)

    # Load into new layer
    layer2 = FogOfWarLayer(10, 10, file_path=fow_path)
    assert layer2.explored_mask[0, 0] == 255
    assert layer2.explored_mask[1, 1] == 0
