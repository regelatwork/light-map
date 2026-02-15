import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import GestureType, AppMode, MenuActions
from light_map.menu_system import MenuSystemState
from light_map.menu_builder import build_root_menu
from light_map.map_config import MapConfigManager

# Mock MediaPipe Results (Copied from test_interactive_app.py)
class MockHandLandmark:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z

class MockResults:
    def __init__(
        self,
        hands_landmarks=None,
        labels=None,
    ):
        if hands_landmarks:
            self.multi_hand_landmarks = [
                MagicMock(landmark=lm) for lm in hands_landmarks
            ]
            self.multi_handedness = []
            for label in labels or ["Right"] * len(hands_landmarks):
                classification = MagicMock()
                classification.label = label
                self.multi_handedness.append(MagicMock(classification=[classification]))
        else:
            self.multi_hand_landmarks = None
            self.multi_handedness = None

@pytest.fixture
def app_config():
    matrix = np.eye(3, dtype=np.float32)
    # Create a mock MapConfigManager for building the menu
    mock_map_config = MagicMock(spec=MapConfigManager)
    mock_map_config.data = MagicMock() # Mock the 'data' attribute
    mock_map_config.data.maps = {}
    mock_map_config.get_map_status.return_value = {'calibrated': False, 'has_session': False}
    mock_map_config.get_ppi.return_value = 96.0 # Default PPI
    mock_map_config.get_map_viewport.return_value = MagicMock() # Mock get_map_viewport

    config = AppConfig(
        width=100, height=100, projector_matrix=matrix, map_search_patterns=[]
    )
    return config, mock_map_config

@pytest.fixture
def app(app_config):
    _app_config, mock_map_config = app_config
    _app = InteractiveApp(_app_config)
    # Also mock the internal map_config instance within the app
    _app.map_config = mock_map_config
    # Manually set the root menu after app initialization to bypass initial build_root_menu call
    _app.menu_system.set_root_menu(build_root_menu(_app.map_config))
    return _app

def test_close_menu_switches_to_viewing(app):
    app.mode = AppMode.MENU
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Mock MenuSystem to return CLOSE_MENU action
    with patch.object(app.menu_system, "update") as mock_update:
        mock_state = MagicMock()
        mock_state.just_triggered_action = MenuActions.CLOSE_MENU
        mock_state.is_visible = True
        mock_update.return_value = mock_state

        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])
        app.process_frame(frame, results)

        assert app.mode == AppMode.VIEWING

def test_load_map_switches_to_viewing(app):
    app.mode = AppMode.MENU
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Mock MenuSystem to return LOAD_MAP action
    with patch.object(app.menu_system, "update") as mock_update:
        mock_state = MagicMock()
        mock_state.just_triggered_action = "LOAD_MAP|test.svg"
        mock_state.is_visible = True
        mock_update.return_value = mock_state

        # Mock SVGLoader
        with patch("light_map.interactive_app.SVGLoader") as MockLoader:
            loader_instance = MagicMock()
            MockLoader.return_value = loader_instance
            loader_instance.detect_grid_spacing.return_value = (50.0, 0.0, 0.0)

            results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])
            app.process_frame(frame, results)

            assert app.mode == AppMode.VIEWING

def test_viewing_mode_ignores_pan_zoom(app):
    app.mode = AppMode.VIEWING

    # Initialize Map State
    app.map_system.state.x = 0.0
    app.map_system.state.zoom = 1.0

    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # 1. Try Pan (Closed Fist)
    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.CLOSED_FIST

        # Frame 1
        results1 = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])
        app.process_frame(frame, results1)

        # Frame 2 (Moved)
        results2 = MockResults(hands_landmarks=[[MockHandLandmark(0.6, 0.5)] * 21])
        app.process_frame(frame, results2)

        # Should NOT have moved
        assert app.map_system.state.x == 0.0

    # 2. Try Zoom (Two Pointing Hands)
    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.POINTING

        h1 = [MockHandLandmark(0.4, 0.5)] * 21
        h2 = [MockHandLandmark(0.6, 0.5)] * 21
        results = MockResults(hands_landmarks=[h1, h2])

        app.time_provider = MagicMock(return_value=1.0)
        app.process_frame(frame, results)

        app.time_provider.return_value = 2.0
        # Check internal state - zoom_gesture_start_time should NOT be set/updated for interaction
        # Actually _process_viewing_mode doesn't look for pointing/zoom at all.
        # So we just check map state remains 1.0
        assert app.map_system.state.zoom == 1.0

def test_viewing_mode_shaka_toggles_tokens(app):
    app.mode = AppMode.VIEWING
    app.show_tokens = True  # Default
    app.time_provider = MagicMock(return_value=10.0)  # Ensure past delay

    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.SHAKA
        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])

        # Trigger
        app.process_frame(frame, results)

        assert app.show_tokens is False

def test_viewing_mode_summon_menu(app):
    app.mode = AppMode.VIEWING
    app.time_provider = MagicMock(return_value=0.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.VICTORY  # SUMMON_GESTURE
        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])

        # 1. Start Summon
        app.time_provider.return_value = 1.0
        app.process_frame(frame, results)
        assert app.mode == AppMode.VIEWING

        # 2. Complete Summon
        app.time_provider.return_value = 2.5  # > 1.0s
        app.process_frame(frame, results)

        assert app.mode == AppMode.MENU
        assert app.menu_system.state == MenuSystemState.WAITING_FOR_NEUTRAL
