import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import Token, SceneId, GmPosition
from light_map.map_config import MapConfigManager, ResolvedToken
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
    mock_map_config.data.global_settings = MagicMock()
    mock_map_config.data.global_settings.gm_position = GmPosition.SOUTH
    mock_map_config.get_map_status.return_value = {
        "calibrated": False,
        "has_session": False,
    }
    mock_map_config.get_ppi.return_value = 96.0  # Default PPI
    mock_map_config.get_map_viewport.return_value = MagicMock()  # Mock get_map_viewport

    config = AppConfig(
        width=1000,
        height=1000,
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


def test_draw_ghost_tokens_unknown(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True

    # One known, one unknown
    app.map_system.ghost_tokens = [
        Token(id=1, world_x=100, world_y=100),
        Token(id=2, world_x=200, world_y=200),
    ]

    # Mock world_to_screen
    app.map_system.world_to_screen = MagicMock(side_effect=[(100, 100), (200, 200)])

    # Mock resolve_token_profile
    app.app_context.map_config_manager.resolve_token_profile.side_effect = [
        ResolvedToken(name="Fighter", type="PC", size=1, height_mm=10.0, is_known=True),
        ResolvedToken(
            name="Unknown Token #2", type="NPC", size=1, height_mm=10.0, is_known=False
        ),
    ]

    with (
        patch("cv2.circle") as mock_circle,
        patch("cv2.putText") as mock_putText,
        patch(
            "light_map.vision.overlay_renderer.draw_dashed_circle"
        ) as mock_dashed_circle,
    ):
        # Trigger a render via OverlayLayer
        ws = WorldState()
        ws.tokens = app.map_system.ghost_tokens
        ws.tokens_timestamp = 1
        app.overlay_layer.state = ws
        app.overlay_layer.render()

        # Verify that circles were drawn
        assert mock_circle.called or mock_dashed_circle.called
        assert mock_putText.called


def test_draw_ghost_tokens_duplicate(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True

    # One primary, one duplicate
    app.map_system.ghost_tokens = [
        Token(id=10, world_x=100, world_y=100, is_duplicate=False),
        Token(id=10, world_x=300, world_y=300, is_duplicate=True),
    ]

    # Mock world_to_screen
    app.map_system.world_to_screen = MagicMock(side_effect=[(100, 100), (300, 300)])

    # Mock resolve_token_profile
    app.app_context.map_config_manager.resolve_token_profile.return_value = (
        ResolvedToken(name="Goblin", type="NPC", size=1, height_mm=10.0, is_known=True)
    )

    ws = WorldState()
    ws.tokens = app.map_system.ghost_tokens
    ws.tokens_timestamp = 1

    with (
        patch("cv2.circle") as mock_circle,
        patch("cv2.putText"),
        patch(
            "light_map.vision.overlay_renderer.draw_dashed_circle"
        ) as mock_dashed_circle,
    ):
        app.overlay_layer.state = ws
        app.overlay_layer.render()

        assert mock_dashed_circle.called
        assert mock_circle.called


def test_token_name_position(app):
    app.current_scene = app.scenes[SceneId.VIEWING]
    app.app_context.show_tokens = True

    # Setup a ghost token at (500, 500)
    app.map_system.ghost_tokens = [
        Token(id=1, world_x=500, world_y=500),
    ]
    app.map_system.world_to_screen = MagicMock(return_value=(500, 500))
    app.app_context.map_config_manager.get_ppi.return_value = 100.0

    # Resolved token info (size 1 inch = 100 pixels, so radius = 50)
    app.app_context.map_config_manager.resolve_token_profile.return_value = (
        ResolvedToken(
            name="Test Hero", type="PC", size=1, height_mm=25.0, is_known=True
        )
    )

    ws = WorldState()
    ws.tokens = app.map_system.ghost_tokens
    ws.tokens_timestamp = 1

    with patch("cv2.putText") as mock_putText:
        app.overlay_layer.state = ws
        app.overlay_layer.render()

        # Check if name was drawn at expected position (offset from 500, 500)
        found = False
        for call in mock_putText.call_args_list:
            args, _ = call
            if args[1] == "Test Hero":
                pos = args[2]
                # Expected roughly (500-radius, 500+radius+20) = (400, 620)
                assert 390 <= pos[0] <= 410
                assert 610 <= pos[1] <= 630
                found = True
        assert found
