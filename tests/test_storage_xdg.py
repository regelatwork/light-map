import os
import shutil
import pytest
from light_map.core.storage import StorageManager
from light_map.map_config import MapConfigManager
from light_map.session_manager import SessionManager
from light_map.common_types import SessionData, ViewportState


@pytest.fixture
def storage_mock(tmp_path, monkeypatch):
    base_dir = tmp_path / "xdg_sim"
    storage = StorageManager(base_dir=str(base_dir))
    storage.ensure_dirs()

    # Monkeypatch the default storage objects in the modules
    monkeypatch.setattr("light_map.session_manager._DEFAULT_STORAGE", storage)
    monkeypatch.setattr(
        "light_map.session_manager.SESSION_DIR",
        os.path.join(storage.get_data_dir(), "sessions"),
    )
    monkeypatch.setattr("light_map.map_config._DEFAULT_STORAGE", storage)
    monkeypatch.setattr(
        "light_map.map_config.STATE_FILE", storage.get_config_path("map_state.json")
    )
    monkeypatch.setattr("light_map.common_types._DEFAULT_STORAGE", storage)

    return storage


def test_map_config_default_path(storage_mock):
    # Initialize MapConfigManager without explicit storage, should use mock
    config_mgr = MapConfigManager()

    # Check if the filename is correctly set to the mock XDG path
    expected_path = storage_mock.get_config_path("map_state.json")
    assert config_mgr.filename == expected_path

    # Save something and verify it exists
    config_mgr.save()
    assert os.path.exists(expected_path)


def test_session_manager_default_path(storage_mock):
    map_path = "/tmp/test_map.svg"
    data = SessionData(map_file=map_path, viewport=ViewportState(), tokens=[])

    # Test saving WITHOUT explicit session_dir (should use mock XDG path)
    if os.path.exists("sessions"):
        shutil.rmtree("sessions")

    SessionManager.save_for_map(map_path, data)
    assert not os.path.exists("sessions"), "Should NOT create local sessions/ directory"

    expected_session_path = SessionManager.get_session_path(map_path)
    assert expected_session_path.startswith(storage_mock.get_data_dir())
    assert os.path.exists(expected_session_path)


def test_map_config_manager_session_status_storage(storage_mock):
    config_mgr = MapConfigManager()
    map_path = os.path.abspath("test_map.svg")

    # Manually create a session in the storage dir
    data = SessionData(map_file=map_path, viewport=ViewportState(), tokens=[])
    SessionManager.save_for_map(map_path, data)

    # Register map in config
    from light_map.map_config import MapEntry

    config_mgr.data.maps[map_path] = MapEntry(grid_spacing_svg=10.0)

    status = config_mgr.get_map_status(map_path)
    assert status["has_session"] is True
