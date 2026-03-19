import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from light_map.core.app_context import AppContext
from light_map.scenes.calibration_scenes import ProjectorCalibrationScene
from light_map.common_types import AppConfig, SceneId
from light_map.core.scene import SceneTransition


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.notifications = MagicMock()
    mock_context.last_camera_frame = None
    return mock_context


def test_projector_calibration_flow_success(mock_app_context):
    """Verify successful projector calibration flow."""
    scene = ProjectorCalibrationScene(mock_app_context)
    mock_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_app_context.last_camera_frame = mock_frame

    mock_time = 0.0

    def mock_monotonic():
        nonlocal mock_time
        return mock_time

    with (
        patch("time.monotonic", side_effect=mock_monotonic),
        patch(
            "light_map.projector.compute_projector_homography",
            return_value=(np.eye(3), [], []),
        ),
    ):
        scene.on_enter()
        assert scene._stage == "DISPLAY_PATTERN"

        # Advance to SETTLE
        mock_time += 1.1
        scene.update([], [], mock_time)
        assert scene._stage == "SETTLE"

        # Advance to CAPTURE
        mock_time += 2.1
        scene.update([], [], mock_time)
        assert scene._stage == "CAPTURE"

        # Advance to PROCESSING/DONE
        transition = scene.update([], [], mock_time)

        assert scene._stage == "DONE"
        assert isinstance(transition, SceneTransition)
        assert transition.target_scene == SceneId.MENU
        mock_app_context.notifications.add_notification.assert_called_with(
            "Projector calibrated successfully."
        )


def test_projector_calibration_no_camera_error(mock_app_context):
    """Verify error handling when no camera is available."""
    scene = ProjectorCalibrationScene(mock_app_context)
    mock_app_context.last_camera_frame = None

    mock_time = 0.0

    def mock_monotonic():
        nonlocal mock_time
        return mock_time

    with patch("time.monotonic", side_effect=mock_monotonic):
        scene.on_enter()

        # To SETTLE
        mock_time += 1.1
        scene.update([], [], mock_time)

        # To CAPTURE
        mock_time += 2.1
        scene.update([], [], mock_time)

        # Process and fail
        transition = scene.update([], [], mock_time)

        assert scene._stage == "ERROR"
        assert isinstance(transition, SceneTransition)
        assert transition.target_scene == SceneId.MENU
        mock_app_context.notifications.add_notification.assert_called_with(
            "Error: No camera frame captured."
        )


def test_projector_calibration_render(mock_app_context):
    """Verify render output during pattern display."""
    scene = ProjectorCalibrationScene(mock_app_context)
    scene.on_enter()  # Sets stage to DISPLAY_PATTERN

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    output = scene.render(frame)

    # Should NOT be all white (pattern has black squares)
    assert not np.all(output == 255)
    # Should NOT be all black
    assert not np.all(output == 0)
    # Background should be white (255)
    assert output[0, 0, 0] == 255


def test_projector_calibration_isolated_layers(mock_app_context):
    """Verify that ProjectorCalibrationScene isolates its layers to avoid interference."""
    scene = ProjectorCalibrationScene(mock_app_context)
    mock_app = MagicMock()
    mock_app.scene_layer = "scene"
    mock_app.token_layer = "token"
    mock_app.menu_layer = "menu"
    mock_app.notification_layer = "notification"
    mock_app.debug_layer = "debug"
    mock_app.cursor_layer = "cursor"

    layers = scene.get_active_layers(mock_app)

    assert "scene" in layers
    assert "token" in layers
    assert "menu" in layers
    assert "cursor" in layers

    # Notification and Debug layers are excluded to avoid pattern interference
    assert "notification" not in layers
    assert "debug" not in layers
    assert len(layers) == 4
