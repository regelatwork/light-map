import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# We need to patch cv2 BEFORE importing Camera if it does things at import time (it doesn't here).
# But we need to patch cv2.VideoCapture inside the Camera class.

from src.light_map.camera import Camera

@patch('src.light_map.camera.Camera._is_raspberry_pi')
@patch('cv2.VideoCapture')
def test_camera_initialization_standard(mock_capture, mock_is_pi):
    # Setup mock
    mock_is_pi.return_value = False
    mock_instance = MagicMock()
    mock_capture.return_value = mock_instance
    mock_instance.isOpened.return_value = True
    
    # Test
    cam = Camera(index=1)
    
    # Verify
    mock_capture.assert_called_with(1)
    assert cam.cap == mock_instance

@patch('cv2.VideoCapture')
def test_camera_read_success(mock_capture):
    mock_instance = MagicMock()
    mock_capture.return_value = mock_instance
    mock_instance.isOpened.return_value = True
    
    # Mock reading a frame
    fake_frame = "image_data"
    mock_instance.read.return_value = (True, fake_frame)
    
    cam = Camera()
    frame = cam.read()
    
    assert frame == fake_frame
    mock_instance.read.assert_called_once()

@patch('cv2.VideoCapture')
def test_camera_context_manager(mock_capture):
    mock_instance = MagicMock()
    mock_capture.return_value = mock_instance
    mock_instance.isOpened.return_value = True
    
    with Camera() as cam:
        pass
        
    # Should be released after exit
    mock_instance.release.assert_called_once()
