import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.scenes.calibration_scenes import ExtrinsicsCalibrationScene
from light_map.core.scene import HandInput
from light_map.gestures import GestureType
from light_map.common_types import SceneId


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.app_config.width = 1920
    context.app_config.height = 1080
    context.map_config_manager.get_ppi.return_value = 96.0
    # Add dummy token profile
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

    # Mock return: rvec, tvec, obj_points, img_points
    # obj_points (N, 3), img_points (N, 2)
    obj_pts = np.zeros((4, 3), dtype=np.float32)
    img_pts = np.zeros((4, 2), dtype=np.float32)
    mock_calibrate.return_value = (np.zeros(3), np.zeros(3), obj_pts, img_pts)

    mock_npz = MagicMock()
    # Mock dictionary behavior for np.load context manager
    # Correct way to mock context manager result is usually simpler but here np.load returns an NpzFile object
    # which acts as a dict.
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
    # The scene uses cv2.aruco internally in update() for PLACEMENT stage.
    # We can mock cv2.aruco via patch. But since the logic is inside update,
    # we need to ensure the detection happens.

    # Actually, the scene logic calls detector.detectMarkers directly.
    # Let's patch cv2.aruco.ArucoDetector in the test function scope.
    with (
        patch("cv2.aruco.ArucoDetector") as MockDetector,
        patch("cv2.aruco.getPredefinedDictionary"),
        patch("cv2.aruco.DetectorParameters"),
    ):
        detector_instance = MockDetector.return_value

        # Return 3 detected markers (ID 1, 2, 3) near targets TL, TR, BL
        # Target zones: (200, 200), (1720, 200), (200, 880)
        ids = np.array([[1], [2], [3]], dtype=np.int32)
        corners = (
            np.array(
                [[[195, 195], [205, 195], [205, 205], [195, 205]]], dtype=np.float32
            ),  # Near TL
            np.array(
                [[[1715, 195], [1725, 195], [1725, 205], [1715, 205]]], dtype=np.float32
            ),  # Near TR
            np.array(
                [[[195, 875], [205, 875], [205, 885], [195, 885]]], dtype=np.float32
            ),  # Near BL
        )
        detector_instance.detectMarkers.return_value = (corners, ids, [])

        # Simulate Fist gesture
        inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), None)]

        # Call update to trigger detection and transition to CAPTURE (implied logic check)
        # The update loop logic:
        # 1. PLACEMENT: detect markers. If valid_count >= 3 and FIST -> CAPTURE.
        scene.update(inputs, 1.0)

        # Now stage should be CAPTURE
        assert scene._stage == "CAPTURE"

        # Call update again to execute CAPTURE logic
        scene.update(inputs, 1.1)

        # Verify calibrate_extrinsics was called
        assert mock_calibrate.called

        # Verify arguments
        args, kwargs = mock_calibrate.call_args

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


@patch("light_map.scenes.calibration_scenes.calibrate_extrinsics")
@patch("light_map.scenes.calibration_scenes.save_camera_extrinsics")
def test_extrinsics_scene_validation_flow(mock_save, mock_calibrate, mock_context):
    # Setup
    mock_context.camera_matrix = np.eye(3)
    mock_context.dist_coeffs = np.zeros(5)

    # Mock return: rvec, tvec, obj_points, img_points
    obj_pts = np.array(
        [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=np.float32
    )
    img_pts = np.array(
        [[100, 100], [110, 100], [100, 110], [100, 100]], dtype=np.float32
    )  # Dummy
    rvec = np.zeros((3, 1))
    tvec = np.zeros((3, 1))

    mock_calibrate.return_value = (rvec, tvec, obj_pts, img_pts)

    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()
    scene._stage = "CAPTURE"  # Force stage

    # 1. Update (CAPTURE -> VALIDATION)
    scene.update([], 1.0)

    assert scene._stage == "VALIDATION"
    assert scene._reprojection_error >= 0.0
    mock_save.assert_not_called()  # Should not save yet

    # 2. Validation - Retry Flow
    # Hold Fist for 1.0s (not enough)
    inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), None)]
    scene.update(inputs, 2.0)  # Start retry
    assert scene._retry_gesture_start_time == 2.0
    assert scene._stage == "VALIDATION"

    # Hold for another 2.5s (> 2s total)
    scene.update(inputs, 4.6)
    assert scene._stage == "PLACEMENT"  # Should reset
    assert scene._retry_gesture_start_time == 0.0

    # 3. Validation - Accept Flow
    scene._stage = "CAPTURE"  # Reset manually for test
    scene.update([], 5.0)  # CAPTURE -> VALIDATION
    assert scene._stage == "VALIDATION"

    inputs = [HandInput(GestureType.VICTORY, (0, 0), None)]
    transition = scene.update(inputs, 6.0)

    assert transition is not None
    assert transition.target_scene == SceneId.MENU
    mock_save.assert_called_once()
