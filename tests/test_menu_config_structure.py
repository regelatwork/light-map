import pytest
from unittest.mock import MagicMock
from light_map.common_types import MenuActions
from light_map.menu_builder import build_root_menu
from light_map.map_config import MapConfigManager


@pytest.fixture
def root_menu():
    mock_map_config = MagicMock(spec=MapConfigManager)
    mock_map_config.data = MagicMock()  # Mock the 'data' attribute
    mock_map_config.data.maps = {}
    mock_map_config.get_map_status.return_value = {
        "calibrated": False,
        "has_session": False,
    }
    return build_root_menu(mock_map_config)


def test_root_menu_structure(root_menu):
    # 1. Verify Top Item is Close/Back
    top_item = root_menu.children[0]
    assert top_item.title == "< Close"
    assert top_item.action_id == MenuActions.CLOSE_MENU
    assert top_item.should_close_on_trigger

    # 2. Verify Bottom Item is Quit
    bottom_item = root_menu.children[-1]
    assert bottom_item.title == "Quit"
    assert bottom_item.action_id == MenuActions.EXIT
    assert bottom_item.should_close_on_trigger

    # 3. Verify other items exist
    titles = [c.title for c in root_menu.children]
    assert "Map Controls" in titles
    assert "Map Settings" in titles
    assert "Calibration" in titles
    assert "Options" in titles


def test_calibration_submenu(root_menu):
    # Find Calibration
    calib_menu = next(c for c in root_menu.children if c.title == "Calibration")

    # Verify children
    sub_titles = [c.title for c in calib_menu.children]
    assert "1. Camera Intrinsics" in sub_titles
    assert "2. Projector Homography" in sub_titles
    assert "3. Physical PPI" in sub_titles
    assert "4. Camera Extrinsics" in sub_titles


def test_map_settings_submenu(root_menu):
    # Find Map Settings
    map_settings = next(c for c in root_menu.children if c.title == "Map Settings")

    # Verify children
    sub_titles = [c.title for c in map_settings.children]
    assert "Rotate CW" in sub_titles
    assert "Rotate CCW" in sub_titles
    assert "Reset View" in sub_titles
    assert "Calibrate PPI" in sub_titles
    assert "Set Scale" in sub_titles
    assert "Zoom 1:1" in sub_titles


def test_session_submenu_items(root_menu):
    session_menu = next(c for c in root_menu.children if c.title == "Session")
    session_titles = [c.title for c in session_menu.children]
    assert "Scan & Save" in session_titles
    assert "Calibrate Flash" in session_titles
    assert "Load Last Session" in session_titles
