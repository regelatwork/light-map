import pytest
import numpy as np
from unittest.mock import patch
from light_map.calibration import (
    load_calibration_images,
    find_corners,
    calibrate_camera_from_images,
)


@pytest.fixture
def mock_cv2():
    with patch("light_map.calibration.cv2") as mock:
        # Defaults for commonly used cv2 functions
        mock.CALIB_CB_ADAPTIVE_THRESH = 1
        mock.CALIB_CB_FAST_CHECK = 2
        mock.CALIB_CB_NORMALIZE_IMAGE = 4
        mock.TERM_CRITERIA_EPS = 1
        mock.TERM_CRITERIA_MAX_ITER = 2
        yield mock


def test_load_calibration_images(tmp_path):
    # Create dummy images
    d = tmp_path / "images"
    d.mkdir()
    (d / "img1.jpg").write_text("content")
    (d / "img2.jpeg").write_text("content")
    (d / "ignore.txt").write_text("content")

    files = load_calibration_images(str(d))
    assert len(files) == 2
    assert any("img1.jpg" in f for f in files)
    assert any("img2.jpeg" in f for f in files)


def test_find_corners_success(mock_cv2):
    # Setup
    mock_image = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_gray = np.zeros((100, 100), dtype=np.uint8)
    mock_cv2.cvtColor.return_value = mock_gray

    # Mock finding corners
    mock_corners = np.array([[[10, 10]]], dtype=np.float32)
    mock_cv2.findChessboardCorners.return_value = (True, mock_corners)
    mock_cv2.cornerSubPix.return_value = (
        mock_corners  # Refined same as initial for test
    )

    # Test
    ret, corners, gray = find_corners(mock_image, (6, 9), (3, 30, 0.1))

    # Verify
    assert ret is True
    assert corners is not None
    assert gray is mock_gray
    mock_cv2.findChessboardCorners.assert_called_once()
    mock_cv2.cornerSubPix.assert_called_once()


def test_find_corners_failure(mock_cv2):
    # Setup
    mock_image = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cv2.findChessboardCorners.return_value = (False, None)

    # Test
    ret, corners, gray = find_corners(mock_image, (6, 9), None)

    # Verify
    assert ret is False
    assert corners is None


def test_calibrate_camera_from_images_success(mock_cv2):
    # Setup
    paths = ["img1.jpg"]
    mock_cv2.imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    # Mock find_corners logic internal to the function
    # The function calls find_corners, which calls cv2 functions.
    # Since we patched 'light_map.calibration.cv2', the internal calls are mocked.
    mock_cv2.findChessboardCorners.return_value = (True, np.zeros((54, 1, 2)))

    # Mock calibrateCamera return
    expected_matrix = np.eye(3)
    expected_dist = np.zeros(5)
    mock_cv2.calibrateCamera.return_value = (
        0.0,
        expected_matrix,
        expected_dist,
        [],
        [],
    )

    # Test
    matrix, dist = calibrate_camera_from_images(paths, (6, 9))

    # Verify
    assert np.array_equal(matrix, expected_matrix)
    assert np.array_equal(dist, expected_dist)
    mock_cv2.calibrateCamera.assert_called_once()


def test_calibrate_camera_no_corners(mock_cv2):
    # Setup
    paths = ["img1.jpg"]
    mock_cv2.imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cv2.findChessboardCorners.return_value = (False, None)

    # Test & Verify
    with pytest.raises(RuntimeError, match="No chessboard corners found"):
        calibrate_camera_from_images(paths)
