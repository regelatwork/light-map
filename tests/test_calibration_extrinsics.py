import pytest
import numpy as np
import cv2
from light_map.calibration_logic import calibrate_extrinsics


def test_calibrate_extrinsics_synthetic():
    # Setup Camera Intrinsics
    camera_matrix = np.array(
        [[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # Setup Pose (R, t)
    # Rotation: ~180 degrees around X (looking down) + 10 degree tilt
    rotation_vector_true = np.array([np.pi + np.radians(10), 0, 0], dtype=np.float32)
    # Translation: (100, 200, 1200)
    translation_vector_true = np.array([100, 200, 1200], dtype=np.float32)

    # Setup World Points (X, Y, Z in mm)
    # 4 points at Z=25 (tokens)
    ppi = 100.0
    ppi_mm = ppi / 25.4

    # Projector Coordinates for tokens
    projector_coords = [[100, 100], [500, 100], [100, 400], [500, 400]]
    known_targets = {1: (100, 100), 2: (500, 100), 3: (100, 400), 4: (500, 400)}
    token_heights = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}
    token_sizes = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

    object_points = []
    for i, (px, py) in enumerate(projector_coords):
        wx = px / ppi_mm
        wy = py / ppi_mm
        wz = 25.0
        object_points.append([wx, wy, wz])

    object_points = np.array(object_points, dtype=np.float32)

    # Project to Image Points (u, v)
    image_points, _ = cv2.projectPoints(
        object_points,
        rotation_vector_true,
        translation_vector_true,
        camera_matrix,
        distortion_coefficients,
    )
    image_points = image_points.reshape(-1, 2)

    # Helper to compare rotation vectors
    def rotation_vector_diff(r1, r2):
        R1, _ = cv2.Rodrigues(r1)
        R2, _ = cv2.Rodrigues(r2)
        return np.linalg.norm(R1 - R2)

    with pytest.MonkeyPatch.context() as mp:

        class MockDetector:
            def detectMarkers(self, frame):
                corners = []
                # In the test, token_sizes[id] = 1.0 inch, ppi = 100.0 => 100 pixels
                # But our true object points were just the centers.
                # We need to project the ACTUAL 4 corners of each token to get the image points.
                size_inches = 1.0
                size_px = size_inches * ppi
                offsets = [
                    [-size_px / 2, -size_px / 2],
                    [size_px / 2, -size_px / 2],
                    [size_px / 2, size_px / 2],
                    [-size_px / 2, size_px / 2],
                ]

                for i, (px_c, py_c) in enumerate(projector_coords):
                    # Derive world corners for this token
                    w_corners = []
                    for dx, dy in offsets:
                        w_corners.append(
                            [(px_c + dx) / ppi_mm, (py_c + dy) / ppi_mm, 25.0]
                        )

                    w_corners = np.array(w_corners, dtype=np.float32)
                    img_corners, _ = cv2.projectPoints(
                        w_corners,
                        rotation_vector_true,
                        translation_vector_true,
                        camera_matrix,
                        distortion_coefficients,
                    )
                    corners.append(img_corners.reshape(1, 4, 2))

                ids = np.array([[1], [2], [3], [4]], dtype=np.int32)
                return corners, ids, []

        mp.setattr(cv2.aruco, "ArucoDetector", lambda *args: MockDetector())
        mp.setattr(cv2, "cvtColor", lambda frame, *args: frame)

        # Ground Points (Z=0)
        ground_points = object_points.copy()
        ground_points[:, 2] = 0
        image_points_ground, _ = cv2.projectPoints(
            ground_points,
            rotation_vector_true,
            translation_vector_true,
            camera_matrix,
            distortion_coefficients,
        )
        image_points_ground = image_points_ground.reshape(-1, 2)

        projector_matrix, _ = cv2.findHomography(
            image_points_ground, np.array(projector_coords, dtype=np.float32)
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Test 1: Only Tokens (Z > 0) with known_targets
        result = calibrate_extrinsics(
            frame,
            projector_matrix,
            camera_matrix,
            distortion_coefficients,
            token_heights,
            ppi,
            known_targets=known_targets,
            token_sizes=token_sizes,
        )

        assert result is not None
        rotation_vector_res, translation_vector_res, _, _ = result
        assert rotation_vector_diff(rotation_vector_res, rotation_vector_true) < 0.1
        assert (
            np.linalg.norm(translation_vector_res.flatten() - translation_vector_true)
            < 5.0
        )

        # Test 2: Combined (Ground + Tokens) with known_targets
        result_combined = calibrate_extrinsics(
            frame,
            projector_matrix,
            camera_matrix,
            distortion_coefficients,
            token_heights,
            ppi,
            ground_points_camera=image_points_ground,
            ground_points_projector=np.array(projector_coords, dtype=np.float32),
            known_targets=known_targets,
            token_sizes=token_sizes,
        )

        assert result_combined is not None
        rotation_vector_comb, translation_vector_comb, _, _ = result_combined
        assert rotation_vector_diff(rotation_vector_comb, rotation_vector_true) < 0.05
        assert (
            np.linalg.norm(translation_vector_comb.flatten() - translation_vector_true)
            < 1.0
        )
