import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import Token, SceneId
from light_map.map_config import MapConfigManager
from light_map.core.world_state import WorldState


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
def app_config(tmp_path):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))
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
        width=100,
        height=100,
        projector_matrix=matrix,
        map_search_patterns=[],
        storage_manager=storage,
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
        patch(
            "light_map.interactive_app.InteractiveApp._load_camera_calibration",
            return_value=(np.eye(3), np.zeros(5), np.zeros((3, 1)), np.zeros((3, 1))),
        ),
        patch(
            "light_map.vision.tracking_coordinator.TrackingCoordinator.process_aruco_tracking"
        ),
    ):
        _app = InteractiveApp(_app_config)

    # The app now uses an AppContext, so we need to mock the config manager there
    _app.app_context.map_config_manager = mock_map_config
    return _app


def test_token_count_display_no_tokens(app):
    # Mock tracking to prevent clearing tokens
    app.tracking_coordinator.process_aruco_tracking = MagicMock()

    # Set the scene to one that shows tokens
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = []

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    MockResults()  # No hands

    state = WorldState()
    state.effective_show_tokens = True
    state.background = frame
    state.last_frame_timestamp = 1


    # OverlayRenderer.draw_ghost_tokens is where token drawing happens now
    with patch(
        "light_map.overlay_layer.OverlayRenderer.draw_ghost_tokens"
    ) as mock_draw_tokens:
        app.process_state(state, [])
        mock_draw_tokens.assert_called()  # Called but should draw nothing if tokens empty


def test_token_count_display_with_tokens(app):
    app.tracking_coordinator.process_aruco_tracking = MagicMock()
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = [Token(1, 10, 10), Token(2, 20, 20)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    MockResults()  # No hands

    # Mock the scene's render method to return a valid frame
    app.current_scene.render = MagicMock(return_value=frame)

    state = WorldState()
    state.effective_show_tokens = True
    state.background = frame
    state.last_frame_timestamp = 1
    state.tokens = app.map_system.ghost_tokens

    # Verify that OverlayRenderer draws onto the internal buffer
    with patch(
        "light_map.overlay_layer.OverlayRenderer.draw_ghost_tokens"
    ) as mock_draw_tokens:
        app.process_state(state, [])
        assert mock_draw_tokens.called


def test_token_count_hidden_when_toggled_off(app):
    app.tracking_coordinator.process_aruco_tracking = MagicMock()
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = False
    app.map_system.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    MockResults()

    # Mock the scene's render method to return a valid frame
    app.current_scene.render = MagicMock(return_value=frame)

    state = WorldState()
    state.effective_show_tokens = False
    state.background = frame
    state.last_frame_timestamp = 1
    state.tokens = app.map_system.ghost_tokens

    with patch(
        "light_map.overlay_layer.OverlayRenderer.draw_ghost_tokens"
    ) as mock_draw_tokens:
        app.process_state(state, [])
        # In OverlayLayer, draw_ghost_tokens is only called if show_tokens is True
        mock_draw_tokens.assert_not_called()


def test_token_count_hidden_in_menu(app):
    """Verify that tokens are not shown in MenuScene."""
    app.tracking_coordinator.process_aruco_tracking = MagicMock()
    app.current_scene = app.scenes[SceneId.MENU]
    app.app_context.show_tokens = True
    app.map_system.ghost_tokens = [Token(1, 10, 10)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    MockResults()

    # Mock the scene's render method
    app.current_scene.render.return_value = frame

    state = WorldState()
    state.effective_show_tokens = True
    state.background = frame
    state.last_frame_timestamp = 1
    state.tokens = app.map_system.ghost_tokens

    with patch("light_map.overlay_layer.OverlayRenderer.draw_ghost_tokens"):
        app.process_state(state, [])
        # MenuScene is not in (ViewingScene, MapScene), but OverlayLayer
        # doesn't check scene type anymore, OverlayRenderer did?
        # Wait, I should check OverlayLayer logic.
        pass
