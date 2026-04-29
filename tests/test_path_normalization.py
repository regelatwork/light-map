import os
from unittest.mock import MagicMock, patch

import pytest

from light_map.map.map_config import MapConfigManager
from light_map.map.session_manager import SessionManager


@pytest.fixture
def mock_map_config():
    """Fixture to create a MapConfigManager with a temporary state file."""
    # Use a temporary file for isolation
    config = MapConfigManager(filename="test_map_state.json")
    # Clear any previous test data
    config.data.maps = {}
    config.save()
    yield config
    # Teardown: remove the test file
    if os.path.exists("test_map_state.json"):
        os.remove("test_map_state.json")


def test_map_config_save_viewport_normalizes_path(mock_map_config):
    """Verify MapConfigManager normalizes paths on save."""
    relative_path = "maps/test.svg"
    absolute_path = os.path.abspath(relative_path)

    mock_map_config.save_map_viewport(relative_path, 10, 20, 1.5, 90)

    # Verify that the data is stored under the absolute path
    assert absolute_path in mock_map_config.data.maps
    assert relative_path not in mock_map_config.data.maps
    assert mock_map_config.data.maps[absolute_path].viewport.x == 10


def test_map_config_get_viewport_normalizes_path(mock_map_config):
    """Verify MapConfigManager normalizes paths on get."""
    relative_path = "maps/test.svg"
    absolute_path = os.path.abspath(relative_path)

    # Manually insert data with an absolute path
    mock_map_config.data.maps[absolute_path] = MagicMock()
    mock_map_config.data.maps[absolute_path].viewport.x = 100

    # Retrieve using the relative path
    viewport = mock_map_config.get_map_viewport(relative_path)

    # Verify that the correct data was retrieved
    assert viewport.x == 100


def test_session_manager_get_session_path_uses_abspath():
    """Verify SessionManager uses the absolute path to generate session filenames."""
    relative_path = "maps/another_map.svg"
    absolute_path = os.path.abspath(relative_path)

    # Mock os.path.abspath to track its calls
    with patch("os.path.abspath", return_value=absolute_path) as mock_abspath:
        SessionManager.get_session_path(relative_path)
        # We expect it to be called once within get_session_path
        mock_abspath.assert_called_once_with(relative_path)

    # Also check the inverse: providing an absolute path should not call it again
    with patch("os.path.abspath", return_value=absolute_path) as mock_abspath:
        SessionManager.get_session_path(absolute_path)
        # If the path is already absolute, it might not be called again.
        # This is an implementation detail, but the core is that the hash is
        # derived from the absolute path. Let's check the generated path.
        path1 = SessionManager.get_session_path(relative_path)
        path2 = SessionManager.get_session_path(absolute_path)
        assert path1 == path2
