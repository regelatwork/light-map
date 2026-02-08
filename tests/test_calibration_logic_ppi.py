import pytest
import numpy as np
import cv2
from light_map.calibration_logic import calculate_ppi_from_frame

def test_calculate_ppi_success():
    # Create a dummy frame with two squares
    frame = np.zeros((500, 500, 3), dtype=np.uint8)
    frame[:] = (255, 255, 255) # White background
    
    # Draw two black squares
    # Distance 100px
    # Marker 1 at (100, 250)
    # Marker 2 at (200, 250)
    cv2.rectangle(frame, (90, 240), (110, 260), (0, 0, 0), -1)
    cv2.rectangle(frame, (190, 240), (210, 260), (0, 0, 0), -1)
    
    # Identity matrix (Camera px = Projector px)
    matrix = np.eye(3, dtype=np.float32)
    
    ppi = calculate_ppi_from_frame(frame, matrix, target_dist_mm=25.4) # 1 inch
    
    # Distance is 100px. Target is 1 inch. PPI should be 100.
    assert ppi is not None
    assert pytest.approx(ppi, abs=1.0) == 100.0

def test_calculate_ppi_no_markers():
    frame = np.zeros((500, 500, 3), dtype=np.uint8)
    frame[:] = (255, 255, 255)
    matrix = np.eye(3, dtype=np.float32)
    
    ppi = calculate_ppi_from_frame(frame, matrix)
    assert ppi is None
