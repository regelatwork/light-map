import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.scenes.calibration_scenes import ExtrinsicsCalibrationScene
from light_map.core.scene import HandInput
from light_map.gestures import GestureType


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.app_config.width = 1920
    context.app_config.height = 1080
    context.map_config_manager.get_ppi.return_value = 96.0
    context.map_config_manager.data.global_settings.aruco_defaults = {
        1: MagicMock(profile="medium"),
        2: MagicMock(profile="medium"),
        3: MagicMock(profile="medium"),
    }
    context.map_config_manager.resolve_token_profile.return_value.height_mm = 25.0
    context.projector_matrix = np.eye(3)
    context.camera_matrix = np.eye(3)
    context.dist_coeffs = np.zeros(5)
    context.last_camera_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    return context


@patch("light_map.scenes.calibration_scenes.calibrate_extrinsics")
@patch("numpy.load")
@patch("os.path.exists")
def test_extrinsics_scene_uses_ground_points(
    mock_exists, mock_load, mock_calibrate, mock_context
):
    # Setup mock projector_calibration.npz
    mock_exists.return_value = True

    # Mock data in npz
    cam_pts = np.array([[100, 100], [200, 200]], dtype=np.float32)
    proj_pts = np.array([[150, 150], [250, 250]], dtype=np.float32)

    mock_calibrate.return_value = (np.zeros(3), np.zeros(3))

    mock_npz = MagicMock()
    mock_npz.__getitem__.side_effect = lambda key: {
        "camera_points": cam_pts,
        "projector_points": proj_pts,
    }[key]
    mock_load.return_value = mock_npz

    # Initialize Scene
    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()

    # Check if file was loaded
    mock_load.assert_called_with("projector_calibration.npz")

    # Trigger Capture
    # We need to simulate detection of markers.

    with patch("cv2.aruco.ArucoDetector") as MockDetector:
        detector_instance = MockDetector.return_value

        # Return 3 detected markers (ID 1, 2, 3)
        ids = np.array([[1], [2], [3]], dtype=np.int32)
        corners = [
            np.array([[[10, 10], [20, 10], [20, 20], [10, 20]]], dtype=np.float32),
            np.array([[[30, 30], [40, 30], [40, 40], [30, 40]]], dtype=np.float32),
            np.array([[[50, 50], [60, 50], [60, 60], [50, 60]]], dtype=np.float32),
        ]
        detector_instance.detectMarkers.return_value = (corners, ids, [])

        # Simulate Fist gesture
        inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), None)]

        # Call update to trigger detection and transition to CAPTURE
        scene.update(inputs, 1.0)

        # Call update again to execute CAPTURE logic
        scene.update(inputs, 1.1)

        # Verify calibrate_extrinsics was called
        assert mock_calibrate.called

        # Verify arguments
        args, kwargs = mock_calibrate.call_args

        print(f"Call args: {args}")
        print(f"Call kwargs: {kwargs}")

        # If passed as kwargs:
        if "ground_points_cam" in kwargs:
            np.testing.assert_array_equal(kwargs["ground_points_cam"], cam_pts)
            np.testing.assert_array_equal(kwargs["ground_points_proj"], proj_pts)
        else:
            # If passed as args, they are at index 6 and 7
            if len(args) > 6:
                np.testing.assert_array_equal(args[6], cam_pts)
                np.testing.assert_array_equal(args[7], proj_pts)
            else:
                pytest.fail(
                    "ground_points_cam and ground_points_proj were not passed to calibrate_extrinsics"
                )
