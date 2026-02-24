import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from light_map.core.app_context import AppContext
from light_map.scenes.scanning_scene import ScanningScene, ScanStage
from light_map.common_types import AppConfig, SceneId
from light_map.core.scene import SceneTransition


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)
    mock_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Configure nested mocks
    mock_context.map_config_manager = MagicMock()
    mock_context.map_config_manager.get_flash_intensity.return_value = 255
    mock_context.map_system = MagicMock()
    mock_context.map_system.svg_loader = MagicMock()
    mock_context.map_system.svg_loader.filename = "test.svg"
    mock_context.map_config_manager.data.maps.get.return_value = None
    mock_context.map_config_manager.get_ppi.return_value = 96.0
    mock_context.notifications = MagicMock()
    mock_context.camera_rvec = np.zeros(3)
    mock_context.camera_tvec = np.zeros(3)

    return mock_context


def test_scanning_scene_state_machine(mock_app_context):
    """Verify the state machine transitions of the ScanningScene."""
    scene = ScanningScene(mock_app_context)

    mock_time = 0.0

    def mock_monotonic():
        nonlocal mock_time
        return mock_time

    with patch("time.monotonic", side_effect=mock_monotonic):
        # Initial state
        scene.on_enter()
        assert scene._stage == ScanStage.START

        # START -> FLASH
        mock_time += 0.1
        scene.update([], mock_time)
        assert scene._stage == ScanStage.FLASH

        # FLASH -> CAPTURE_FLASH (after delay)
        mock_time += 1.6  # 1.7s total
        scene.update([], mock_time)
        assert scene._stage == ScanStage.CAPTURE_FLASH

        # CAPTURE_FLASH -> PROCESS
        mock_time += 0.1  # 0.1s total
        scene.update([], mock_time)
        assert scene._stage == ScanStage.PROCESS

        # PROCESS -> SHOW_RESULT (happens within render)
        with patch.object(scene, "_detect_and_save_tokens") as mock_detect:
            scene.render(np.zeros((100, 100, 3), dtype=np.uint8))
            mock_detect.assert_called_once_with(mock_app_context.last_camera_frame)
        assert scene._stage == ScanStage.SHOW_RESULT

        # SHOW_RESULT -> DONE (after delay)
        mock_time += 2.01  # 2.81s total, 2.01s elapsed since SHOW_RESULT
        transition = scene.update([], mock_time)
        assert scene._stage == ScanStage.DONE
        assert isinstance(transition, SceneTransition)
        assert transition.target_scene == SceneId.MAP


def test_render_flash(mock_app_context):
    """Verify that the scene renders a white frame during the FLASH stage."""
    scene = ScanningScene(mock_app_context)
    mock_time = 0.0
    with patch("time.monotonic", return_value=mock_time):
        scene.on_enter()
        scene.update([], mock_time)  # Move to FLASH stage
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        rendered_frame = scene.render(frame)
        assert np.all(rendered_frame == 255)


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
