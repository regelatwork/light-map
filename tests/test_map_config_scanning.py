import pytest
from unittest.mock import patch
from light_map.map.map_config import MapConfigManager, MapEntry


@pytest.fixture
def mock_config_file(tmp_path):
    return str(tmp_path / "test_map_state.json")


def test_scan_for_maps_adds_new_maps(mock_config_file):
    manager = MapConfigManager(mock_config_file)

    with (
        patch("glob.glob") as mock_glob,
        patch("os.path.isfile") as mock_isfile,
        patch("os.path.abspath") as mock_abspath,
        patch("os.path.exists") as mock_exists,
    ):
        # Setup mocks
        mock_glob.return_value = ["/maps/dungeon.svg", "/maps/cave.png"]
        mock_abspath.side_effect = lambda x: x  # Return as is
        mock_isfile.return_value = True
        mock_exists.return_value = True  # Assume they exist for pruning check

        # Execute
        result = manager.scan_for_maps(["/maps/*"])

        # Verify
        assert "/maps/dungeon.svg" in result
        assert "/maps/cave.png" in result
        assert len(manager.data.maps) == 2
        assert manager.data.maps["/maps/dungeon.svg"].last_seen != ""


def test_scan_for_maps_prunes_missing_maps(mock_config_file):
    manager = MapConfigManager(mock_config_file)

    # Pre-populate with a map
    manager.data.maps["/maps/old.svg"] = MapEntry()

    with (
        patch("glob.glob") as mock_glob,
        patch("os.path.isfile") as mock_isfile,
        patch("os.path.abspath") as mock_abspath,
        patch("os.path.exists") as mock_exists,
    ):
        # Setup mocks
        mock_glob.return_value = ["/maps/new.svg"]
        mock_abspath.side_effect = lambda x: x
        mock_isfile.return_value = True

        # os.path.exists logic:
        # returns True for /maps/new.svg (so it's added)
        # returns False for /maps/old.svg (so it's pruned)
        def exists_side_effect(path):
            if path == "/maps/new.svg":
                return True
            if path == "/maps/old.svg":
                return False
            if path == "test_map_state.json":
                return False  # For initial load check
            return False

        mock_exists.side_effect = exists_side_effect

        # Execute
        result = manager.scan_for_maps(["/maps/*"])

        # Verify
        assert "/maps/new.svg" in result
        assert "/maps/old.svg" not in result
        assert len(manager.data.maps) == 1


def test_forget_map(mock_config_file):
    manager = MapConfigManager(mock_config_file)
    manager.data.maps["/maps/todelete.svg"] = MapEntry()

    manager.forget_map("/maps/todelete.svg")

    assert "/maps/todelete.svg" not in manager.data.maps


def test_get_map_status(mock_config_file):
    manager = MapConfigManager(mock_config_file)
    manager.data.maps["/maps/calibrated.svg"] = MapEntry(grid_spacing_svg=10.0)
    manager.data.maps["/maps/uncalibrated.svg"] = MapEntry(grid_spacing_svg=0.0)

    with patch(
        "light_map.map.map_config.SessionManager.has_session"
    ) as mock_has_session:
        mock_has_session.return_value = True

        status1 = manager.get_map_status("/maps/calibrated.svg")
        assert status1["calibrated"] is True
        assert status1["has_session"] is True

        status2 = manager.get_map_status("/maps/uncalibrated.svg")
        assert status2["calibrated"] is False

        status3 = manager.get_map_status("/maps/unknown.svg")
        assert status3["calibrated"] is False
