import cv2
import numpy as np
import os
import pytest
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem

def test_aruco_fov_masking():
    # Setup mock calibration
    K = np.array(
        [[1000.0, 0.0, 320.0], [0.0, 1000.0, 240.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist = np.zeros(5, dtype=np.float32)
    R = np.eye(3, dtype=np.float32)
    rvec, _ = cv2.Rodrigues(R)
    tvec = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    np.savez("test_fov_cam_calib.npz", camera_matrix=K, dist_coeffs=dist)
    np.savez("test_fov_cam_ext.npz", rvec=rvec, tvec=tvec)

    detector = ArucoTokenDetector(
        calibration_file="test_fov_cam_calib.npz", extrinsics_file="test_fov_cam_ext.npz",
        debug_mode=True
    )

    # Create synthetic frame with two ArUco markers
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    
    # Marker 1 at (100, 100)
    frame[60:140, 60:140] = 255
    marker1 = cv2.aruco.generateImageMarker(aruco_dict, 1, 50)
    frame[75:125, 75:125] = cv2.cvtColor(marker1, cv2.COLOR_GRAY2BGR)
    
    # Marker 2 at (400, 400)
    frame[360:440, 360:440] = 255
    marker2 = cv2.aruco.generateImageMarker(aruco_dict, 2, 50)
    frame[375:425, 375:425] = cv2.cvtColor(marker2, cv2.COLOR_GRAY2BGR)

    map_system = MapSystem(640, 480)
    
    # Identity projector matrix: (0,0)->(0,0), (640,480)->(640,480)
    # Mask will be the whole 640x480 frame.
    projector_matrix_full = np.eye(3, dtype=np.float32)

    # 1. Detect WITHOUT masking
    tokens_no_mask = detector.detect(frame, map_system)
    assert len(tokens_no_mask) == 2

    # 2. Detect WITH full masking (should still see both)
    tokens_full_mask = detector.detect(frame, map_system, projector_matrix=projector_matrix_full)
    assert len(tokens_full_mask) == 2

    # 3. Detect WITH partial masking (Top-Left 200x200)
    # Projector size 200x200.
    map_system_small = MapSystem(200, 200)
    # Identity projector matrix means projector pixels (0-200, 0-200) map to camera (0-200, 0-200).
    tokens_masked = detector.detect(frame, map_system_small, projector_matrix=projector_matrix_full)
    
    # It should only see Marker 1 (at 100, 100)
    assert len(tokens_masked) == 1
    assert tokens_masked[0].id == 1

    # 4. Detect WITH shifted masking (Bottom-Right area)
    # Let's say the projector pixels (0,0) to (200,200) map to camera area (300, 300) to (500, 500)
    # This means cx = px + 300, cy = py + 300.
    # The projector_matrix parameter in detect() is defined as the mapping from PROJECTOR to CAMERA.
    projector_matrix_shifted = np.array([[1.0, 0.0, 300.0], [0.0, 1.0, 300.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    
    print("\nDetecting with shifted matrix...")
    # Map system is 200x200
    tokens_shifted = detector.detect(frame, map_system_small, projector_matrix=projector_matrix_shifted, ppi=25.4)
    print(f"Detected tokens: {[t.id for t in tokens_shifted]}")
    
    # Marker 1 is at camera (100, 100) -> Outside (300, 300, 500, 500)
    # Marker 2 center is at camera (400, 400) -> Inside (300, 300, 500, 500)
    assert len(tokens_shifted) == 1
    assert tokens_shifted[0].id == 2

    # Cleanup
    os.remove("test_fov_cam_calib.npz")
    os.remove("test_fov_cam_ext.npz")

if __name__ == "__main__":
    pytest.main([__file__])
