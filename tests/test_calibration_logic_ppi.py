import pytest
import numpy as np
import cv2
from light_map.calibration_logic import calculate_ppi_from_frame


def test_calculate_ppi_success():
    # Create a dummy frame with two ArUco markers
    frame = np.zeros((500, 500, 3), dtype=np.uint8)
    frame[:] = (255, 255, 255)  # White background

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Generate Marker 0
    m0 = cv2.aruco.generateImageMarker(aruco_dict, 0, 40)  # 40px
    # Generate Marker 1
    m1 = cv2.aruco.generateImageMarker(aruco_dict, 1, 40)

    # Convert to BGR
    m0 = cv2.cvtColor(m0, cv2.COLOR_GRAY2BGR)
    m1 = cv2.cvtColor(m1, cv2.COLOR_GRAY2BGR)

    # Place Marker 0 at (100, 250) (Center ~ 120, 270)
    # Let's put top-left at specific coords
    # Center of Marker 0: (120, 270)
    frame[250:290, 100:140] = m0

    # Place Marker 1 at (200, 250) -> Center (220, 270)
    # Distance between centers = 100px
    frame[250:290, 200:240] = m1

    # Identity matrix (Camera px = Projector px)
    matrix = np.eye(3, dtype=np.float32)

    ppi = calculate_ppi_from_frame(frame, matrix, target_dist_mm=25.4)  # 1 inch

    # Distance is 100px. Target is 1 inch. PPI should be 100.
    assert ppi is not None
    assert pytest.approx(ppi, abs=2.0) == 100.0


def test_calculate_ppi_no_markers():
    frame = np.zeros((500, 500, 3), dtype=np.uint8)
    frame[:] = (255, 255, 255)
    matrix = np.eye(3, dtype=np.float32)

    ppi = calculate_ppi_from_frame(frame, matrix)
    assert ppi is None
