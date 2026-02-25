import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.calibration_logic import run_calibration_sequence, calibrate_extrinsics
from light_map.camera import Camera


@pytest.fixture
def mock_cv2():
    with patch("light_map.calibration_logic.cv2") as mock:
        yield mock


@pytest.fixture
def mock_camera():
    mock = MagicMock(spec=Camera)
    # Mock return value for read()
    mock.read.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    return mock


@pytest.fixture
def mock_projector_utils():
    with (
        patch("light_map.calibration_logic.generate_calibration_pattern") as mock_gen,
        patch(
            "light_map.calibration_logic.compute_projector_homography"
        ) as mock_compute,
    ):
        mock_gen.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), "params")
        mock_compute.return_value = np.eye(3)
        yield mock_gen, mock_compute


@pytest.fixture
def mock_projector_window():
    with patch("light_map.calibration_logic.ProjectorWindow") as mock:
        instance = mock.return_value
        instance.is_closed.return_value = False
        yield mock


def test_run_calibration_sequence_success(
    mock_cv2, mock_camera, mock_projector_utils, mock_projector_window
):
    mock_gen, mock_compute = mock_projector_utils
    mock_win = mock_projector_window.return_value

    # Run
    result = run_calibration_sequence(
        mock_camera, projector_width=1920, projector_height=1080
    )

    # Verify
    assert result is not None
    assert np.array_equal(result, np.eye(3))

    # Interactions
    mock_projector_window.assert_called_once()
    assert mock_win.update_image.call_count >= 21  # 1 initial + 20 in loop
    # We expect read() to be called: 5 flush + 1 capture
    assert mock_camera.read.call_count >= 6
    mock_cv2.imwrite.assert_called_once()
    mock_compute.assert_called_once()
    mock_win.close.assert_called_once()


def test_run_calibration_sequence_capture_failure(
    mock_cv2, mock_camera, mock_projector_utils, mock_projector_window
):
    mock_gen, mock_compute = mock_projector_utils
    mock_camera.read.return_value = None  # Fail capture
    mock_win = mock_projector_window.return_value

    # Run
    result = run_calibration_sequence(mock_camera)

    # Verify
    assert result is None
    mock_compute.assert_not_called()
    mock_win.close.assert_called_once()  # Ensure cleanup


def test_run_calibration_sequence_exception(
    mock_cv2, mock_camera, mock_projector_utils, mock_projector_window
):
    mock_gen, mock_compute = mock_projector_utils
    mock_compute.side_effect = ValueError("Calculation error")
    mock_win = mock_projector_window.return_value

    # Run
    result = run_calibration_sequence(mock_camera)

    # Verify
    assert result is None
    mock_win.close.assert_called_once()  # Ensure cleanup


def test_calibrate_extrinsics_flip_inverted(mock_cv2):
    # Setup mock for solvePnP to return tz < 0
    mock_cv2.solvePnP.return_value = (
        True,
        np.zeros((3, 1)),
        np.array([[0.0], [0.0], [-1000.0]], dtype=np.float32),
    )

    # Mock Rodrigues for flip logic
    mock_cv2.Rodrigues.side_effect = lambda x: (
        (np.eye(3), None) if x.ndim == 2 else (np.eye(3), None)
    )

    # Mock ArUco detector
    mock_detector = MagicMock()
    mock_detector.detectMarkers.return_value = ([], None, [])
    mock_cv2.aruco.ArucoDetector.return_value = mock_detector

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    proj_matrix = np.eye(3)
    cam_matrix = np.eye(3)
    dist_coeffs = np.zeros(5)

    # Run
    result = calibrate_extrinsics(
        frame,
        proj_matrix,
        cam_matrix,
        dist_coeffs,
        token_heights={1: 5.0},
        ppi=100.0,
        ground_points_cam=np.array([[50, 50], [60, 60], [70, 70], [80, 80]]),
        ground_points_proj=np.array([[100, 100], [120, 120], [140, 140], [160, 160]]),
    )

    assert result is not None
    rvec, tvec, obj_pts, img_pts = result

    # Verify tz is now positive
    assert tvec[2] > 0
    # Check it called solvePnP with useExtrinsicGuess and SQPNP
    args, kwargs = mock_cv2.solvePnP.call_args
    assert kwargs["useExtrinsicGuess"] is True
    assert kwargs["flags"] == mock_cv2.SOLVEPNP_SQPNP
