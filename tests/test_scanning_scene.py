import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from light_map.core.app_context import AppContext
from light_map.vision.scanning_scene import ScanningScene, ScanStage
from light_map.core.common_types import AppConfig, SceneId
from light_map.core.scene import SceneTransition


from light_map.state.temporal_event_manager import TemporalEventManager


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)
    mock_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    mock_time = 0.0

    def mock_monotonic():
        return mock_time

    mock_context.time_provider = mock_monotonic
    mock_context.events = TemporalEventManager(time_provider=mock_monotonic)

    # Configure nested mocks
    mock_context.map_config_manager = MagicMock()
    mock_context.map_config_manager.get_flash_intensity.return_value = 255
    mock_context.map_system = MagicMock()
    mock_context.map_system.svg_loader = MagicMock()
    mock_context.map_system.svg_loader.filename = "test.svg"
    mock_context.map_config_manager.data.maps.get.return_value = None
    mock_context.map_config_manager.get_ppi.return_value = 96.0
    mock_context.notifications = MagicMock()

    # Use numpy arrays for rotation and translation to satisfy OpenCV requirements
    mock_context.camera_matrix = np.eye(3, dtype=np.float32)
    mock_context.distortion_coefficients = np.zeros(5, dtype=np.float32)
    mock_context.camera_rotation_vector = np.zeros((3, 1), dtype=np.float32)
    mock_context.camera_translation_vector = np.zeros((3, 1), dtype=np.float32)

    return mock_context


def test_scanning_scene_state_machine(mock_app_context):
    """Verify the state machine transitions of the ScanningScene."""
    scene = ScanningScene(mock_app_context)

    # Use a mutable object to hold time so it can be updated inside closures
    class TimeState:
        val = 0.0

    time_state = TimeState()

    def mock_monotonic():
        return time_state.val

    mock_app_context.time_provider = mock_monotonic
    mock_app_context.events.time_provider = mock_monotonic

    with patch("time.monotonic", side_effect=mock_monotonic):
        # Initial state
        scene.on_enter()
        assert scene._stage == ScanStage.START

        # START -> FLASH
        time_state.val += 0.1
        scene.update([], [], time_state.val)
        assert scene._stage == ScanStage.FLASH

        # FLASH -> CAPTURE_FLASH (after delay)
        time_state.val += 1.6  # 1.7s total
        mock_app_context.events.check()
        assert (
            scene._stage == ScanStage.PROCESS
        )  # CAPTURE_FLASH immediately transitions to PROCESS

        # PROCESS -> SHOW_RESULT (happens within _change_stage for PROCESS)
        with patch.object(scene, "_detect_and_save_tokens") as mock_detect:
            # Manually trigger process stage update
            scene._change_stage(ScanStage.PROCESS, time_state.val)
            mock_detect.assert_called_once_with(mock_app_context.last_camera_frame)
        assert scene._stage == ScanStage.SHOW_RESULT

        # SHOW_RESULT -> DONE (after delay)
        time_state.val += 2.01  # 3.71s total
        mock_app_context.events.check()
        assert scene._stage == ScanStage.DONE

        transition = scene.update([], [], time_state.val)
        assert isinstance(transition, SceneTransition)
        assert transition.target_scene == SceneId.MAP


def test_render_flash(mock_app_context):
    """Verify that the scene includes FlashLayer during the FLASH stage."""
    scene = ScanningScene(mock_app_context)
    mock_time = 0.0
    with patch("time.monotonic", return_value=mock_time):
        scene.on_enter()
        scene.update([], [], mock_time)  # Move to FLASH stage

        mock_app = MagicMock()
        mock_app.flash_layer = MagicMock()
        layers = scene.get_active_layers(mock_app)
        assert mock_app.flash_layer in layers


def test_debug_mode_propagation(mock_app_context):
    """Verify that debug mode is propagated to TokenTracker."""
    mock_app_context.debug_mode = True
    scene = ScanningScene(mock_app_context)

    # Mock TokenTracker
    with patch.object(scene.token_tracker, "detect_tokens"):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Manually trigger detection logic
        scene._detect_and_save_tokens(frame)

        assert scene.token_tracker.debug_mode is True
