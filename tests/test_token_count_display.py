import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import Token, SceneId
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
    # Only patch scenes that have complex initialization dependencies
    with (
        patch("light_map.interactive_app.MenuScene"),
        patch("light_map.interactive_app.ScanningScene"),
        patch("light_map.interactive_app.FlashCalibrationScene"),
        patch("light_map.interactive_app.MapGridCalibrationScene"),
        patch("light_map.interactive_app.PpiCalibrationScene"),
    ):
        _app = InteractiveApp(_app_config)

    # The app now uses an AppContext, so we need to mock the config manager there
    _app.app_context.map_config_manager = mock_map_config
    return _app


def test_token_count_display_no_tokens(app):
    # Set the scene to one that shows tokens
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = []

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    # Since rendering is now more complex, let's mock the overlay method
    # and check that the token drawing sub-method isn't called.
    with patch.object(app, "_draw_ghost_tokens") as mock_draw_tokens:
        app.process_frame(frame, results)
        mock_draw_tokens.assert_not_called()


def test_token_count_display_with_tokens(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = [Token(1, 10, 10), Token(2, 20, 20)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()  # No hands

    # Mock the scene's render method to return a valid frame
    app.current_scene.render = MagicMock(return_value=frame)

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


@patch("light_map.interactive_app.InteractiveApp._draw_ghost_tokens")
def test_token_count_hidden_when_toggled_off(mock_draw_tokens, app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = False
    app.map_system.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()

    # Mock the scene's render method to return a valid frame
    app.current_scene.render = MagicMock(return_value=frame)

    with patch("cv2.putText") as mock_putText:
        app.process_frame(frame, results)

        # Assert that the ghost tokens are not drawn
        mock_draw_tokens.assert_not_called()

        # Check that "Tokens: 1 (Hidden)" was drawn
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Tokens: 1 (Hidden)":
                found = True
                break
        assert found, "Token count 'Tokens: 1 (Hidden)' not found"


def test_token_count_hidden_in_menu(app):
    """Verify that tokens are not shown in MenuScene."""
    app.current_scene = app.scenes[SceneId.MENU]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults()

    # Mock the scene's render method
    app.current_scene.render.return_value = frame

    with (
        patch("cv2.putText") as mock_putText,
        patch.object(app, "_draw_ghost_tokens") as mock_draw_tokens,
    ):
        app.process_frame(frame, results)

        # Assert tokens NOT drawn
        mock_draw_tokens.assert_not_called()

        # Assert text NOT drawn
        for call in mock_putText.call_args_list:
            args, _ = call
            assert "Tokens:" not in args[1], (
                f"Token count should not be drawn in MenuScene, found: {args[1]}"
            )
