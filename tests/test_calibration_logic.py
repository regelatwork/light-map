from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.calibration.calibration_logic import (
    run_calibration_sequence,
)
from light_map.vision.infrastructure.camera import Camera


@pytest.fixture
def mock_cv2():
    with patch("light_map.calibration.calibration_logic.cv2") as mock:
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
        patch("light_map.calibration.calibration_logic.generate_calibration_pattern") as mock_gen,
        patch(
            "light_map.calibration.calibration_logic.compute_projector_homography"
        ) as mock_compute,
    ):
        mock_gen.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), "params")
        mock_compute.return_value = np.eye(3)
        yield mock_gen, mock_compute


@pytest.fixture
def mock_projector_window():
    with patch("light_map.calibration.calibration_logic.ProjectorWindow") as mock:
        instance = mock.return_value
        instance.is_closed.return_value = False
        yield mock


def test_run_calibration_sequence_success(
    mock_cv2, mock_camera, mock_projector_utils, mock_projector_window
):
    mock_gen, mock_compute = mock_projector_utils
    mock_win = mock_projector_window.return_value

    # Mock ArUco detector return values
    mock_detector = MagicMock()
    mock_detector.detectMarkers.return_value = ([], None, [])
    mock_cv2.aruco.ArucoDetector.return_value = mock_detector

    # Run
    result = run_calibration_sequence(mock_camera, projector_width=1920, projector_height=1080)

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
