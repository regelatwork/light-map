import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import AppMode, Token
from light_map.menu_builder import build_root_menu
from light_map.map_config import MapConfigManager


# Reuse Mock classes from test_viewing_mode
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
    mock_map_config.data = MagicMock()  # Mock the 'data' attribute
    mock_map_config.data.maps = {}
    mock_map_config.get_map_status.return_value = {
        "calibrated": False,
        "has_session": False,
    }
    mock_map_config.get_ppi.return_value = 96.0  # Default PPI
    mock_map_config.get_map_viewport.return_value = MagicMock()  # Mock get_map_viewport

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


def test_token_count_display_no_tokens(app):
    app.mode = AppMode.VIEWING
    app.show_tokens = True
    app.ghost_tokens = []

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check if "Tokens: 0" was drawn
        # cv2.putText(img, text, org, font, fontScale, color, thickness)
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Tokens: 0":
                found = True
                break
        assert found, "Token count 'Tokens: 0' not found in cv2.putText calls"


def test_token_count_display_with_tokens(app):
    app.mode = AppMode.VIEWING
    app.show_tokens = True
    app.ghost_tokens = [Token(1, 10, 10), Token(2, 20, 20)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check if "Tokens: 2" was drawn
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Tokens: 2":
                found = True
                break
        assert found, "Token count 'Tokens: 2' not found in cv2.putText calls"


def test_token_count_hidden_when_toggled_off(app):
    app.mode = AppMode.VIEWING
    app.show_tokens = False
    app.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Check that NO "Tokens: ..." was drawn
        for call in mock_putText.call_args_list:
            args, _ = call
            if isinstance(args[1], str) and args[1].startswith("Tokens:"):
                pytest.fail(f"Found token count '{args[1]}' when show_tokens is False")
