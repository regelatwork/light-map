import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from light_map.core.app_context import AppContext
from light_map.scenes.calibration_scenes import IntrinsicsCalibrationScene
from light_map.common_types import AppConfig, GestureType, SceneId
from light_map.core.scene import HandInput, SceneTransition


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)
    mock_context.map_config_manager = MagicMock()
    mock_context.notifications = MagicMock()
    return mock_context


@pytest.fixture
def intrinsics_calib_scene(mock_app_context):
    return IntrinsicsCalibrationScene(mock_app_context)


class MockCamera:
    def __init__(self, return_image=None):
        self._return_image = return_image

    def get_frame(self):
        return self._return_image


def test_intrinsics_calibration_capture_and_process(
    intrinsics_calib_scene,
    mock_app_context,
):
    """Verify that capturing and processing chessboard images works."""
    # Setup
    intrinsics_calib_scene.on_enter()
    mock_app_context.notifications.reset_mock()  # Reset mock calls after on_enter

    # Simulate images being available
    mock_app_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch(
        "light_map.scenes.calibration_scenes.process_chessboard_images",
        return_value=((np.eye(3), np.zeros(5)), [np.eye(4)]),
    ) as mock_process_images:
        with patch(
            "light_map.scenes.calibration_scenes.save_camera_calibration"
        ) as mock_save_calibration:
            # Add enough images to trigger processing
            for _ in range(intrinsics_calib_scene._required_images):
                intrinsics_calib_scene.update(
                    [
                        HandInput(
                            gesture=GestureType.CLOSED_FIST,
                            proj_pos=(0, 0),
                            unit_direction=(0.0, 0.0),
                            raw_landmarks=MagicMock(),
                        )
                    ],
                    [],
                    0.0,
                )
            assert (
                len(intrinsics_calib_scene._captured_images)
                == intrinsics_calib_scene._required_images
            )
            assert intrinsics_calib_scene._stage == "PROCESSING"

            mock_app_context.notifications.reset_mock()  # Reset before processing update

            # Now call update again to trigger the PROCESSING stage logic
            intrinsics_calib_scene.update([], [], 0.0)

            mock_process_images.assert_called_once()
            mock_save_calibration.assert_called_once()
            assert intrinsics_calib_scene._stage == "DONE"
            mock_app_context.notifications.add_notification.assert_called_once_with(
                "Camera calibrated successfully."
            )


def test_intrinsics_calibration_process_failure(
    intrinsics_calib_scene, mock_app_context
):
    """Verify error notification on calibration failure."""
    intrinsics_calib_scene.on_enter()
    mock_app_context.notifications.reset_mock()  # Reset mock calls after on_enter
    mock_app_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch(
        "light_map.scenes.calibration_scenes.process_chessboard_images",
        return_value=None,
    ) as mock_process_images:
        # Trigger processing with enough images
        for _ in range(intrinsics_calib_scene._required_images):
            intrinsics_calib_scene.update(
                [
                    HandInput(
                        gesture=GestureType.CLOSED_FIST,
                        proj_pos=(0, 0),
                        unit_direction=(0.0, 0.0),
                        raw_landmarks=MagicMock(),
                    )
                ],
                [],
                0.0,
            )
        assert intrinsics_calib_scene._stage == "PROCESSING"

        mock_app_context.notifications.reset_mock()  # Reset before processing update

        # Now call update again to trigger the PROCESSING stage logic
        intrinsics_calib_scene.update([], [], 0.0)

        mock_process_images.assert_called_once()
        assert intrinsics_calib_scene._stage == "ERROR"
        mock_app_context.notifications.add_notification.assert_called_once_with(
            "Camera calibration failed. Ensure target is visible and well-lit."
        )


def test_intrinsics_calibration_transition_to_menu(intrinsics_calib_scene):
    """Verify transition to MenuScene after calibration is done or if it's in ERROR state."""
    intrinsics_calib_scene.on_enter()

    # Simulate DONE state
    intrinsics_calib_scene._stage = "DONE"
    transition = intrinsics_calib_scene.update([], [], 0.0)
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU

    # Simulate ERROR state
    intrinsics_calib_scene._stage = "ERROR"
    transition = intrinsics_calib_scene.update([], [], 0.0)
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU


def test_intrinsics_calibration_isolated_layers(intrinsics_calib_scene):
    """Verify that IntrinsicsCalibrationScene isolates its layers to avoid interference."""
    mock_app = MagicMock()
    mock_app.scene_layer = "scene"
    mock_app.token_layer = "token"
    mock_app.menu_layer = "menu"
    mock_app.notification_layer = "notification"
    mock_app.debug_layer = "debug"
    mock_app.selection_progress_layer = "selection_progress"
    mock_app.cursor_layer = "cursor"

    layers = intrinsics_calib_scene.get_active_layers(mock_app)

    assert "scene" in layers
    assert "token" in layers
    assert "menu" in layers
    assert "notification" in layers
    assert "debug" in layers
    assert "selection_progress" in layers
    assert "cursor" in layers
    assert len(layers) == 7
