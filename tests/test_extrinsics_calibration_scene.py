import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.scenes.calibration_scenes import ExtrinsicsCalibrationScene
from light_map.core.scene import HandInput
from light_map.gestures import GestureType
from light_map.common_types import SceneId


@pytest.fixture
def mock_context():
    from light_map.common_types import AppConfig

    context = MagicMock()
    context.app_config = AppConfig(
        width=1920,
        height=1080,
        projector_matrix=np.eye(3),
        camera_matrix=np.eye(3),
        distortion_coefficients=np.zeros(5),
    )
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
    context.distortion_coefficients = np.zeros(5)
    context.last_camera_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    context.events = MagicMock()
    context.notifications = MagicMock()
    context.analytics = MagicMock()
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
    camera_points = np.array([[100, 100], [200, 200]], dtype=np.float32)
    projector_points = np.array([[150, 150], [250, 250]], dtype=np.float32)

    # Mock return: rotation_vector, translation_vector, object_points, image_points
    # object_points (N, 3), image_points (N, 2)
    object_points = np.zeros((4, 3), dtype=np.float32)
    image_points = np.zeros((4, 2), dtype=np.float32)
    mock_calibrate.return_value = (
        np.zeros(3),
        np.zeros(3),
        object_points,
        image_points,
    )

    mock_npz = MagicMock()
    # Mock dictionary behavior for np.load context manager
    # Correct way to mock context manager result is usually simpler but here np.load returns an NpzFile object
    # which acts as a dict.
    mock_npz.__getitem__.side_effect = lambda key: {
        "camera_points": camera_points,
        "projector_points": projector_points,
    }[key]
    mock_load.return_value = mock_npz

    # Initialize Scene
    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()

    # Check if file was loaded
    mock_load.assert_called_with("projector_calibration.npz")

    # Simulate detection of markers via AppContext
    # Target zones: TL=(220, 180), TR=(1720+30, 180-20), BL=(220-40, 900+15), BR=(1720-15, 900-35), C=(960+25, 540-10)
    # IDs 1, 2, 3 correspond to existing defaults in mock_context
    mock_context.raw_aruco = {
        "ids": [1, 2, 3],
        "corners": [
            np.array(
                [[195, 195], [205, 195], [205, 205], [195, 205]], dtype=np.float32
            ),  # TL
            np.array(
                [[1715, 195], [1725, 195], [1725, 205], [1715, 205]], dtype=np.float32
            ),  # TR
            np.array(
                [[195, 875], [205, 875], [205, 885], [195, 885]], dtype=np.float32
            ),  # BL
        ],
    }

    # Simulate Fist gesture
    inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), (0.0, 0.0), None)]

    # Call update to trigger detection and transition to CAPTURE (implied logic check)
    # The update loop logic:
    # 1. PLACEMENT: detect markers. If valid_count >= 3 and FIST -> CAPTURE.
    scene.update(inputs, [], 1.0)

    # Now stage should be CAPTURE
    assert scene._stage == "CAPTURE"

    # Call update again to execute CAPTURE logic
    scene.update(inputs, [], 1.1)

    # Verify calibrate_extrinsics was called
    assert mock_calibrate.called

    # Verify arguments
    args, kwargs = mock_calibrate.call_args

    # Check that ground points were passed (now at index 7 and 8 due to new aruco params)
    if "ground_points_camera" in kwargs:
        np.testing.assert_array_equal(kwargs["ground_points_camera"], camera_points)
        np.testing.assert_array_equal(
            kwargs["ground_points_projector"], projector_points
        )
    else:
        # calibrate_extrinsics(frame, projector_matrix, camera_matrix, distortion_coefficients, token_heights, ppi, g_cam, g_proj, ...)
        # Actually it's better to check by name if possible or by position.
        # Current signature: calibrate_extrinsics(frame, projector_matrix, camera_matrix, distortion_coefficients, token_heights, ppi, ground_points_camera, ground_points_projector, ...)
        if len(args) > 7:
            np.testing.assert_array_equal(args[6], camera_points)
            np.testing.assert_array_equal(args[7], projector_points)
        else:
            pytest.fail(
                f"ground_points_camera and ground_points_projector were not passed to calibrate_extrinsics. Args: {len(args)}"
            )


@patch("light_map.scenes.calibration_scenes.calibrate_extrinsics")
@patch("light_map.scenes.calibration_scenes.save_camera_extrinsics")
def test_extrinsics_scene_validation_flow(mock_save, mock_calibrate, mock_context):
    # Setup
    mock_context.camera_matrix = np.eye(3)
    mock_context.distortion_coefficients = np.zeros(5)

    # Mock return: rotation_vector, translation_vector, object_points, image_points
    object_points = np.array(
        [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=np.float32
    )
    image_points = np.array(
        [[100, 100], [110, 100], [100, 110], [100, 100]], dtype=np.float32
    )  # Dummy
    rotation_vector = np.zeros((3, 1))
    translation_vector = np.zeros((3, 1))

    mock_calibrate.return_value = (
        rotation_vector,
        translation_vector,
        object_points,
        image_points,
    )

    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()
    scene._stage = "CAPTURE"  # Force stage

    # 1. Update (CAPTURE -> VALIDATION)
    scene.update([], [], 1.0)

    assert scene._stage == "VALIDATION"
    assert scene._reprojection_error >= 0.0
    mock_save.assert_not_called()  # Should not save yet

    from light_map.common_types import TimerKey

    # 2. Validation - Retry Flow
    mock_context.events.has_event.return_value = False
    inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), (0.0, 0.0), None)]
    scene.update(inputs, [], 2.0)  # Start retry
    assert scene._stage == "VALIDATION"
    mock_context.events.schedule.assert_called_with(
        2.0, scene._on_retry_triggered, key=TimerKey.CALIBRATION_STAGE
    )

    # Trigger it manually for the test
    scene._on_retry_triggered()
    assert scene._stage == "PLACEMENT"

    # 3. Validation - Accept Flow
    scene._stage = "CAPTURE"  # Reset manually for test
    scene.update([], [], 5.0)  # CAPTURE -> VALIDATION
    assert scene._stage == "VALIDATION"

    inputs = [HandInput(GestureType.VICTORY, (0, 0), (0.0, 0.0), None)]
    transition = scene.update(inputs, [], 6.0)

    assert transition is not None
    assert transition.target_scene == SceneId.MENU
    mock_save.assert_called_once()
