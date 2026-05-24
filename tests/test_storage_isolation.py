import os
from pathlib import Path

from light_map.core.storage import StorageManager
from light_map.map.map_config import _DEFAULT_STORAGE as config_storage
from light_map.map.session_manager import _DEFAULT_STORAGE as session_storage


def test_storage_isolation_active():
    """Verify that the test suite is isolated from the user's home directories.

    Specifically asserts that config, data, and state directories are pointing to
    a temporary test directory.
    """
    storage = StorageManager()

    # Get the user's real home directory path
    real_home = str(Path.home())

    # 1. Assert that environment variables are set and point to a temporary test directory
    assert "light_map_test_" in os.environ.get("XDG_CONFIG_HOME", "")
    assert "light_map_test_" in os.environ.get("XDG_DATA_HOME", "")
    assert "light_map_test_" in os.environ.get("XDG_STATE_HOME", "")

    # 2. Assert that StorageManager returns paths inside the temporary directory, NOT under the real home directory default locations
    config_dir = storage.get_config_dir()
    data_dir = storage.get_data_dir()
    state_dir = storage.get_state_dir()

    assert "light_map_test_" in config_dir
    assert "light_map_test_" in data_dir
    assert "light_map_test_" in state_dir

    assert not config_dir.startswith(f"{real_home}/.config/light_map")
    assert not data_dir.startswith(f"{real_home}/.local/share/light_map")
    assert not state_dir.startswith(f"{real_home}/.local/state/light_map")


def test_default_storages_isolated():
    """Assert that the pre-initialized default storage instances in core modules are also isolated."""
    assert "light_map_test_" in config_storage.get_config_dir()
    assert "light_map_test_" in session_storage.get_data_dir()
