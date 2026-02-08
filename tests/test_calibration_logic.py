import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.calibration_logic import run_calibration_sequence
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


def test_run_calibration_sequence_success(mock_cv2, mock_camera, mock_projector_utils):
    mock_gen, mock_compute = mock_projector_utils

    # Run
    result = run_calibration_sequence(mock_camera, width=1920, height=1080)

    # Verify
    assert result is not None
    assert np.array_equal(result, np.eye(3))

    # Interactions
    mock_cv2.namedWindow.assert_called_once()
    mock_cv2.imshow.assert_called_once()
    assert mock_cv2.waitKey.call_count >= 20  # Pump loop
    # We expect read() to be called: 5 flush + 1 capture
    assert mock_camera.read.call_count >= 6
    mock_cv2.imwrite.assert_called_once()
    mock_compute.assert_called_once()
    mock_cv2.destroyWindow.assert_called_once()


def test_run_calibration_sequence_capture_failure(
    mock_cv2, mock_camera, mock_projector_utils
):
    mock_gen, mock_compute = mock_projector_utils
    mock_camera.read.return_value = None  # Fail capture

    # Run
    result = run_calibration_sequence(mock_camera)

    # Verify
    assert result is None
    mock_compute.assert_not_called()
    mock_cv2.destroyWindow.assert_called_once()  # Ensure cleanup


def test_run_calibration_sequence_exception(
    mock_cv2, mock_camera, mock_projector_utils
):
    mock_gen, mock_compute = mock_projector_utils
    mock_compute.side_effect = ValueError("Calculation error")

    # Run
    result = run_calibration_sequence(mock_camera)

    # Verify
    assert result is None
    mock_cv2.destroyWindow.assert_called_once()  # Ensure cleanup
