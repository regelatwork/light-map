import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import (
    MenuItem,
    AppMode,
    ViewportState,
    SessionData,
)


@pytest.fixture
def mock_app_config():
    root = MenuItem(title="Root")
    matrix = np.eye(3)
    return AppConfig(width=100, height=100, projector_matrix=matrix, root_menu=root)


@patch("light_map.interactive_app.SVGLoader")
@patch("light_map.interactive_app.MapConfigManager")
@patch("light_map.interactive_app.MenuSystem")
def test_load_map_action(MockMenuSystem, MockMapConfig, MockSVGLoader, mock_app_config):
    # Setup Mock Config
    mock_config_instance = MockMapConfig.return_value
    mock_entry = MagicMock()
    mock_entry.grid_spacing_svg = 10.0
    mock_entry.scale_factor_1to1 = 1.0
    mock_config_instance.data.maps.get.return_value = mock_entry
    mock_config_instance.get_ppi.return_value = 96.0
    mock_config_instance.get_map_viewport.return_value = ViewportState()

    # Setup App
    app = InteractiveApp(mock_app_config)

    # Simulate LOAD_MAP action
    # We cheat and directly invoke the processing logic or simulate a menu state result

    # Mock MenuState return
    mock_menu_state = MagicMock()
    mock_menu_state.just_triggered_action = "LOAD_MAP|/maps/dungeon.svg"
    app.menu_state = mock_menu_state

    # Call _process_menu_mode (we need to pass dummy hands data)
    # Actually process_frame calls _process_menu_mode
    # But process_frame is complex.
    # We can just check if we can call the action handler logic?
    # No, let's call _process_menu_mode directly if possible, or simulate frame processing.

    # Let's override menu_system.update to return our state
    app.menu_system.update.return_value = mock_menu_state

    # Create dummy hands
    hands = [{"gesture": "None", "proj_pos": (0, 0)}]

    # Execute
    app._process_menu_mode(hands)

    # Verify
    assert app.mode == AppMode.MAP
    assert app.svg_loader is not None  # Mocked
    MockSVGLoader.assert_called_with("/maps/dungeon.svg")


@patch("light_map.interactive_app.SessionManager.load_for_map")
@patch("light_map.interactive_app.SVGLoader")
@patch("light_map.interactive_app.MapConfigManager")
@patch("light_map.interactive_app.MenuSystem")
def test_load_session_action(
    MockMenuSystem, MockMapConfig, MockSVGLoader, MockLoadForMap, mock_app_config
):
    # Setup Mock Config
    mock_config_instance = MockMapConfig.return_value
    mock_entry = MagicMock()
    mock_entry.grid_spacing_svg = 10.0
    mock_entry.scale_factor_1to1 = 1.0
    mock_config_instance.data.maps.get.return_value = mock_entry
    mock_config_instance.get_ppi.return_value = 96.0
    mock_config_instance.get_map_viewport.return_value = ViewportState()

    app = InteractiveApp(mock_app_config)

    # Mock Session Load
    session = SessionData(
        map_file="/maps/saved.svg",
        viewport=ViewportState(x=10, y=10, zoom=2.0),
        tokens=[],
    )
    MockLoadForMap.return_value = session

    # Simulate LOAD_SESSION action
    mock_menu_state = MagicMock()
    mock_menu_state.just_triggered_action = "LOAD_SESSION|/maps/saved.svg"
    app.menu_system.update.return_value = mock_menu_state

    hands = [{"gesture": "None", "proj_pos": (0, 0)}]

    app._process_menu_mode(hands)

    # Verify
    assert app.mode == AppMode.MAP
    MockSVGLoader.assert_called_with("/maps/saved.svg")
    # Check viewport restored (we need to mock MapSystem too or check its state)
    # app.map_system is real.
    assert app.map_system.state.x == 10
    assert app.map_system.state.zoom == 2.0
