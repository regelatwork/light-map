import pytest
import numpy as np
import cv2
from light_map.calibration_logic import calibrate_extrinsics

def test_calibrate_extrinsics_synthetic():
    # Setup Camera Intrinsics
    camera_matrix = np.array([
        [800, 0, 320],
        [0, 800, 240],
        [0, 0, 1]
    ], dtype=np.float32)
    dist_coeffs = np.zeros(5, dtype=np.float32)
    
    # Setup Pose (R, t)
    # Rotation: 30 degrees around X axis
    rvec_true = np.array([np.radians(30), 0, 0], dtype=np.float32)
    # Translation: (100, 200, 1000)
    tvec_true = np.array([100, 200, 1000], dtype=np.float32)
    
    # Setup World Points (X, Y, Z in mm)
    # 4 points at Z=25 (tokens)
    ppi = 100.0
    ppi_mm = ppi / 25.4
    
    # Projector Coordinates for tokens
    proj_coords = [
        [100, 100], [500, 100], [100, 400], [500, 400]
    ]
    known_targets = {1: (100, 100), 2: (500, 100), 3: (100, 400), 4: (500, 400)}
    token_heights = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}
    
    obj_points = []
    for i, (px, py) in enumerate(proj_coords):
        wx = px / ppi_mm
        wy = py / ppi_mm
        wz = 25.0
        obj_points.append([wx, wy, wz])
    
    obj_points = np.array(obj_points, dtype=np.float32)
    
    # Project to Image Points (u, v)
    img_points, _ = cv2.projectPoints(obj_points, rvec_true, tvec_true, camera_matrix, dist_coeffs)
    img_points = img_points.reshape(-1, 2)
    
    # Helper to compare rvecs
    def rvec_diff(r1, r2):
        R1, _ = cv2.Rodrigues(r1)
        R2, _ = cv2.Rodrigues(r2)
        return np.linalg.norm(R1 - R2)

    with pytest.MonkeyPatch.context() as mp:
        class MockDetector:
            def detectMarkers(self, frame):
                corners = []
                for p in img_points:
                    c = np.array([
                        [p[0]-5, p[1]-5], [p[0]+5, p[1]-5], 
                        [p[0]+5, p[1]+5], [p[0]-5, p[1]+5]
                    ], dtype=np.float32).reshape(1, 4, 2)
                    corners.append(c)
                ids = np.array([[1], [2], [3], [4]], dtype=np.int32)
                return corners, ids, []
        
        mp.setattr(cv2.aruco, "ArucoDetector", lambda *args: MockDetector())
        mp.setattr(cv2, "cvtColor", lambda frame, *args: frame) 
        
        # Ground Points (Z=0)
        ground_points = obj_points.copy()
        ground_points[:, 2] = 0
        img_points_ground, _ = cv2.projectPoints(ground_points, rvec_true, tvec_true, camera_matrix, dist_coeffs)
        img_points_ground = img_points_ground.reshape(-1, 2)
        
        projector_matrix, _ = cv2.findHomography(img_points_ground, np.array(proj_coords, dtype=np.float32))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Test 1: Only Tokens (Z > 0) with known_targets
        result = calibrate_extrinsics(
            frame, projector_matrix, camera_matrix, dist_coeffs, token_heights, ppi,
            known_targets=known_targets
        )
        
        assert result is not None
        rvec_res, tvec_res = result
        assert rvec_diff(rvec_res, rvec_true) < 0.1
        assert np.linalg.norm(tvec_res.flatten() - tvec_true) < 5.0

        # Test 2: Combined (Ground + Tokens) with known_targets
        result_combined = calibrate_extrinsics(
            frame, projector_matrix, camera_matrix, dist_coeffs, token_heights, ppi,
            ground_points_cam=img_points_ground,
            ground_points_proj=np.array(proj_coords, dtype=np.float32),
            known_targets=known_targets
        )
        
        assert result_combined is not None
        rvec_comb, tvec_comb = result_combined
        assert rvec_diff(rvec_comb, rvec_true) < 0.05
        assert np.linalg.norm(tvec_comb.flatten() - tvec_true) < 1.0
