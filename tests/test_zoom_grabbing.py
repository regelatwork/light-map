import pytest
from unittest.mock import MagicMock
import numpy as np
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import GestureType, AppMode
from light_map.map_config import MapConfigManager
from light_map.menu_builder import build_root_menu


@pytest.fixture
def app():
    # Minimal Setup
    matrix = np.eye(3)
    mock_map_config = MagicMock(spec=MapConfigManager)
    mock_map_config.data = MagicMock()  # Mock the 'data' attribute
    mock_map_config.data.maps = {}
    mock_map_config.get_map_status.return_value = {
        "calibrated": False,
        "has_session": False,
    }
    mock_map_config.get_ppi.return_value = 96.0
    dynamic_root = build_root_menu(mock_map_config)

    config = AppConfig(
        width=100, height=100, projector_matrix=matrix, map_search_patterns=[]
    )
    # When InteractiveApp is initialized, it will build the menu internally
    _app = InteractiveApp(config)
    # Override the menu_system with the dynamically built one for tests
    _app.menu_system.set_root_menu(dynamic_root)
    # Also mock the internal map_config instance within the app
    _app.map_config = mock_map_config

    _app.mode = AppMode.MAP
    # Mock map system state
    _app.map_system.state.x = 0
    _app.map_system.state.y = 0
    _app.map_system.state.zoom = 1.0
    return _app


def test_zoom_grabbing_symmetric(app):
    # Hands at (40, 50) and (60, 50). Dist=20. Center=(50, 50)
    # Move to (30, 50) and (70, 50). Dist=40. Center=(50, 50)

    # 1. Start Zoom
    hands_start = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (40, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (60, 50),
            "raw_landmarks": MagicMock(),
        },
    ]

    # Init time
    app.time_provider = MagicMock(return_value=1.0)
    app._process_map_mode(hands_start, 1.0)

    # Wait delay
    app._process_map_mode(hands_start, 2.0)  # Trigger start logic

    assert app.zoom_start_dist == 20.0
    # World center under (50, 50) with Pan=0, Zoom=1 is (50, 50)
    assert app.zoom_start_world_center == (50.0, 50.0)

    # 2. Update Zoom (Symmetric expansion)
    hands_end = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (30, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (70, 50),
            "raw_landmarks": MagicMock(),
        },
    ]

    app._process_map_mode(hands_end, 2.1)

    # Check Zoom
    assert app.map_system.state.zoom == 2.0

    # Check Pan
    # Center (50, 50) should still map to World (50, 50)
    # 50 = 50 * 2.0 + PanX => PanX = -50
    assert app.map_system.state.x == -50.0
    assert app.map_system.state.y == -50.0  # Y center was 50, now 50. 50 = 50*2 + PanY


def test_zoom_grabbing_asymmetric_fixed_hand(app):
    # Hands at (40, 50) and (60, 50). Dist=20.
    # Keep Right Hand fixed at (60, 50).
    # Move Left Hand to (20, 50). Dist=40.
    # New Center = (40, 50).

    # 1. Start
    hands_start = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (40, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (60, 50),
            "raw_landmarks": MagicMock(),
        },
    ]
    app.time_provider = MagicMock(return_value=1.0)
    app._process_map_mode(hands_start, 1.0)
    app._process_map_mode(hands_start, 2.0)

    # 2. Update (Left moves left)
    hands_end = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (20, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (60, 50),
            "raw_landmarks": MagicMock(),
        },
    ]

    app._process_map_mode(hands_end, 2.1)

    # Check Zoom
    assert app.map_system.state.zoom == 2.0

    # Check Pan
    # Screen Center = (50, 50)
    # Old World Point under Screen Center = (50, 50)
    # 50 = 50 * 2.0 + PanX => PanX = -50
    assert app.map_system.state.x == -50.0
    assert app.map_system.state.y == -50.0

    # Verification: Midpoint shift
    # New Midpoint is (40, 50)
    # World Point that was at (50, 50) is still at (50, 50) on screen.
    # The map zoomed around the center.


def test_zoom_rotated(app):
    from unittest.mock import MagicMock
    from light_map.common_types import GestureType

    # Setup
    app.map_system.state.rotation = 90
    app.config.width = 100
    app.config.height = 100
    # Ensure map center aligns initially
    app.map_system.state.x = 0
    app.map_system.state.y = 0
    app.map_system.state.zoom = 1.0

    # 1. Start Zoom
    hands_start = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (40, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (60, 50),
            "raw_landmarks": MagicMock(),
        },
    ]

    app.time_provider = MagicMock(return_value=1.0)
    app._process_map_mode(hands_start, 1.0)
    # Wait delay
    app._process_map_mode(hands_start, 2.0)

    assert app.zoom_start_dist == 20.0
    # Center (50, 50) should map to World (50, 50)
    # (Screen->World with Rot=90, Zoom=1, Pan=0)
    # M = S(1) * R(90, 50, 50) * T(0,0)
    # Inverse of R(90 around 50,50) maps 50,50 to 50,50.
    assert app.zoom_start_world_center == pytest.approx((50.0, 50.0))

    # 2. Update Zoom (2x)
    hands_end = [
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (30, 50),
            "raw_landmarks": MagicMock(),
        },
        {
            "gesture": GestureType.POINTING,
            "proj_pos": (70, 50),
            "raw_landmarks": MagicMock(),
        },
    ]

    app._process_map_mode(hands_end, 2.1)

    assert app.map_system.state.zoom == 2.0

    # Check Pan (Derived manually above: x=50, y=-50)
    # The old logic yielded (-50, -50), proving the difference.
    assert app.map_system.state.x == pytest.approx(50.0)
    assert app.map_system.state.y == pytest.approx(-50.0)
