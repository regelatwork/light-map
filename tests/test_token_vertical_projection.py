import pytest
import numpy as np
import cv2
import os
from unittest.mock import patch
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem

def test_token_vertical_projection():
    """
    TDD Test: Verifies that a token's position on the map (Z=0) is derived by 
    projecting its 3D position (at Z=h) vertically down, rather than following 
    the camera ray to Z=0.
    """
    K = np.array([[1000.0, 0.0, 960.0], 
                  [0.0, 1000.0, 540.0], 
                  [0.0, 0.0, 1.0]], dtype=np.float32)
    dist = np.zeros(5, dtype=np.float32)

    # Camera looking down but tilted 30 degrees around X axis (tilting forward)
    angle = np.radians(150) 
    R = np.array([[1, 0, 0],
                  [0, np.cos(angle), -np.sin(angle)],
                  [0, np.sin(angle), np.cos(angle)]], dtype=np.float32)
    
    # Position camera at (0, -500, 866) in world space
    cam_center = np.array([0, -500, 866.0], dtype=np.float32).reshape(3, 1)
    tvec = -R @ cam_center
    rvec, _ = cv2.Rodrigues(R)

    # Create Detector
    np.savez("tdd_cam_calib.npz", camera_matrix=K, dist_coeffs=dist)
    np.savez("tdd_cam_ext.npz", rvec=rvec, tvec=tvec)
    
    # We patch the ArucoDetector class BEFORE creating our wrapper
    with patch("cv2.aruco.ArucoDetector") as MockDetector:
        mock_instance = MockDetector.return_value
        
        detector = ArucoTokenDetector(calibration_file="tdd_cam_calib.npz", 
                                      extrinsics_file="tdd_cam_ext.npz")

        # TOKEN at (100, 200, 0) with marker at (100, 200, 50)
        token_top_world = np.array([100.0, 200.0, 50.0], dtype=np.float32)

        # 3. Find where the marker appears in the CAMERA frame
        p_top_cam = R @ token_top_world.reshape(3, 1) + tvec
        u = K[0,0] * (p_top_cam[0] / p_top_cam[2]) + K[0,2]
        v = K[1,1] * (p_top_cam[1] / p_top_cam[2]) + K[1,2]
        
        u = float(u[0])
        v = float(v[0])

        # Integration Check: detect() method
        map_system = MapSystem(1920, 1080) # Identity mapping mm -> projector pixels -> world
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        # Mock corners: (1, 4, 2)
        c = np.array([[[u-5, v-5], [u+5, v-5], [u+5, v+5], [u-5, v+5]]], dtype=np.float32)
        mock_instance.detectMarkers.return_value = ([c], np.array([[42]]), [])
        
        # ppi=25.4 (1mm = 1px)
        tokens = detector.detect(frame, map_system, ppi=25.4, default_height_mm=50.0)
        
        assert len(tokens) == 1
        t = tokens[0]
        assert t.id == 42
        # Vertical projection to map surface (Z=0)
        assert t.world_x == pytest.approx(100.0, abs=1e-1)
        assert t.world_y == pytest.approx(200.0, abs=1e-1)
        assert t.world_z == 0.0
        # Marker position
        assert t.marker_x == pytest.approx(100.0, abs=1e-1)
        assert t.marker_y == pytest.approx(200.0, abs=1e-1)
        assert t.marker_z == 50.0

    # Cleanup
    if os.path.exists("tdd_cam_calib.npz"): os.remove("tdd_cam_calib.npz")
    if os.path.exists("tdd_cam_ext.npz"): os.remove("tdd_cam_ext.npz")

if __name__ == "__main__":
    test_token_vertical_projection()
