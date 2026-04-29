import os
from unittest.mock import patch

from light_map.core.storage import StorageManager


def test_storage_manager_default_paths():
    """Test that StorageManager returns expected XDG-like paths by default."""
    # We'll mock HOME to ensure deterministic results across different systems
    with patch.dict(os.environ, {"HOME": "/home/testuser"}):
        # Clear XDG vars to test default fallback
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(os.environ, {"HOME": "/home/testuser"}):
                storage = StorageManager()
                # Default Linux behavior: ~/.config/light_map, ~/.local/share/light_map, and ~/.local/state/light_map
                assert storage.get_config_dir().endswith(".config/light_map")
                assert storage.get_data_dir().endswith(".local/share/light_map")
                assert storage.get_state_dir().endswith(".local/state/light_map")


def test_storage_manager_xdg_override():
    """Test that StorageManager respects XDG environment variables."""
    with patch.dict(
        os.environ,
        {
            "XDG_CONFIG_HOME": "/custom/config",
            "XDG_DATA_HOME": "/custom/data",
            "XDG_STATE_HOME": "/custom/state",
        },
    ):
        storage = StorageManager()
        assert storage.get_config_dir() == "/custom/config/light_map"
        assert storage.get_data_dir() == "/custom/data/light_map"
        assert storage.get_state_dir() == "/custom/state/light_map"


def test_storage_manager_base_dir_override():
    """Test that StorageManager respects an explicit base directory override."""
    storage = StorageManager(base_dir="/tmp/light_map_test")
    assert storage.get_config_dir() == "/tmp/light_map_test/config"
    assert storage.get_data_dir() == "/tmp/light_map_test/data"
    assert storage.get_state_dir() == "/tmp/light_map_test/state"


def test_storage_manager_get_path():
    """Test path resolution for specific files."""
    storage = StorageManager(base_dir="/tmp/lm")
    path = storage.get_config_path("map_state.json")
    assert path == "/tmp/lm/config/map_state.json"

    path = storage.get_data_path("camera_calibration.npz")
    assert path == "/tmp/lm/data/camera_calibration.npz"

    path = storage.get_state_path("light_map.log")
    assert path == "/tmp/lm/state/light_map.log"


def test_storage_manager_ensure_dirs(tmp_path):
    """Test that StorageManager can create directories."""
    base = tmp_path / "lm"
    storage = StorageManager(base_dir=str(base))
    storage.ensure_dirs()

    assert os.path.exists(base / "config")
    assert os.path.exists(base / "data")
    assert os.path.exists(base / "state")
