import numpy as np
import os
from light_map.visibility.fow_manager import FogOfWarManager
from light_map.map.map_config import MapConfigManager
from light_map.core.storage import StorageManager


def test_fow_manager_initialization():
    manager = FogOfWarManager(100, 100)
    assert manager.width == 100
    assert manager.height == 100
    assert np.all(manager.explored_mask == 0)
    assert np.all(manager.visible_mask == 0)
    assert manager.is_disabled is False


def test_fow_manager_reveal_area():
    manager = FogOfWarManager(100, 100)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:20, 10:20] = 255

    manager.reveal_area(mask)
    assert np.sum(manager.explored_mask == 255) == 100
    assert manager.explored_mask[15, 15] == 255
    assert manager.explored_mask[0, 0] == 0


def test_fow_manager_set_visible_mask():
    manager = FogOfWarManager(100, 100)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[5:15, 5:15] = 255

    manager.set_visible_mask(mask)
    assert np.sum(manager.visible_mask == 255) == 100
    assert manager.visible_mask[10, 10] == 255
    assert manager.visible_mask[0, 0] == 0


def test_fow_manager_reset():
    manager = FogOfWarManager(100, 100)
    manager.explored_mask.fill(255)
    manager.visible_mask.fill(255)
    manager.reset()
    assert np.all(manager.explored_mask == 0)
    assert np.all(manager.visible_mask == 0)


def test_fow_manager_toggle():
    manager = FogOfWarManager(100, 100)
    assert manager.is_disabled is False
    manager.is_disabled = True
    assert manager.is_disabled is True


def test_fow_persistence_via_config(tmp_path):
    # Setup MapConfigManager with tmp storage
    storage = StorageManager(base_dir=str(tmp_path))
    config = MapConfigManager(storage=storage)

    map_path = "/tmp/test_map.svg"
    manager = FogOfWarManager(10, 10)
    manager.explored_mask[0, 0] = 255
    manager.visible_mask[1, 1] = 255

    # Save
    config.save_fow_masks(map_path, manager)

    fow_dir = config.get_fow_dir(map_path)
    assert os.path.exists(os.path.join(fow_dir, "fow.png"))
    assert os.path.exists(os.path.join(fow_dir, "los.png"))

    # Load into new manager
    manager2 = FogOfWarManager(10, 10)
    config.load_fow_masks(map_path, manager2)
    assert manager2.explored_mask[0, 0] == 255
    assert manager2.visible_mask[1, 1] == 255
    assert manager2.explored_mask[1, 1] == 0
