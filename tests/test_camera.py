from unittest.mock import MagicMock, patch

import pytest

from light_map.vision.infrastructure.camera import Camera


@pytest.fixture
def mock_capture():
    """Patches cv2.VideoCapture and returns the mock object."""
    with patch("cv2.VideoCapture") as mock:
        # Configure the mock instance returned by VideoCapture()
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        # Default behavior: camera is open
        mock_instance.isOpened.return_value = True
        yield mock


@pytest.fixture
def mock_is_pi():
    """Patches Camera._is_raspberry_pi and returns the mock."""
    with patch("light_map.vision.infrastructure.camera.Camera._is_raspberry_pi") as mock:
        mock.return_value = False
        yield mock


def test_camera_initialization_standard(mock_capture, mock_is_pi):
    # Setup
    mock_is_pi.return_value = False

    # Test
    cam = Camera(index=1)

    # Verify
    mock_capture.assert_called_with(1)
    # The instance returned by mock_capture() is what cam.cap should be
    assert cam.cap == mock_capture.return_value


def test_camera_read_success(mock_capture):
    # Setup
    mock_instance = mock_capture.return_value
    fake_frame = "image_data"
    mock_instance.read.return_value = (True, fake_frame)

    # Test
    cam = Camera()
    frame = cam.read()

    # Verify
    assert frame == fake_frame
    mock_instance.read.assert_called_once()


def test_camera_context_manager(mock_capture):
    # Setup
    mock_instance = mock_capture.return_value

    # Test
    with Camera():
        pass

    # Verify
    mock_instance.release.assert_called_once()


def test_camera_pi_pipeline_index_0(mock_capture, mock_is_pi):
    import cv2

    mock_is_pi.return_value = True
    cam = Camera(index=0)
    assert cam.cap == mock_capture.return_value
    args, kwargs = mock_capture.call_args
    pipeline = args[0]
    assert "camera-name=/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a" in pipeline
    assert args[1] == cv2.CAP_GSTREAMER


def test_camera_pi_pipeline_index_1(mock_capture, mock_is_pi):
    import cv2

    mock_is_pi.return_value = True
    cam = Camera(index=1)
    assert cam.cap is not None
    args, kwargs = mock_capture.call_args
    pipeline = args[0]
    assert "camera-name=/base/axi/pcie@1000120000/rp1/i2c@80000/imx708@1a" in pipeline
    assert args[1] == cv2.CAP_GSTREAMER


def test_camera_pi_pipeline_custom_name(mock_capture, mock_is_pi):
    import cv2

    mock_is_pi.return_value = True
    cam = Camera(camera_name="custom_camera_device_path")
    assert cam.cap is not None
    args, kwargs = mock_capture.call_args
    pipeline = args[0]
    assert "camera-name=custom_camera_device_path" in pipeline
    assert args[1] == cv2.CAP_GSTREAMER
