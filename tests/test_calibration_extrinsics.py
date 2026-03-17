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
    # Rotation: 30 degrees around X axis
    rotation_vector_true = np.array([np.radians(30), 0, 0], dtype=np.float32)
    # Translation: (100, 200, 1000)
    translation_vector_true = np.array([100, 200, 1000], dtype=np.float32)

    # Setup World Points (X, Y, Z in mm)
    # 4 points at Z=25 (tokens)
    ppi = 100.0
    ppi_mm = ppi / 25.4

    # Projector Coordinates for tokens
    projector_coords = [[100, 100], [500, 100], [100, 400], [500, 400]]
    known_targets = {1: (100, 100), 2: (500, 100), 3: (100, 400), 4: (500, 400)}
    token_heights = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}

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
                for p in image_points:
                    c = np.array(
                        [
                            [p[0] - 5, p[1] - 5],
                            [p[0] + 5, p[1] - 5],
                            [p[0] + 5, p[1] + 5],
                            [p[0] - 5, p[1] + 5],
                        ],
                        dtype=np.float32,
                    ).reshape(1, 4, 2)
                    corners.append(c)
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
        )

        assert result_combined is not None
        rotation_vector_comb, translation_vector_comb, _, _ = result_combined
        assert rotation_vector_diff(rotation_vector_comb, rotation_vector_true) < 0.05
        assert (
            np.linalg.norm(translation_vector_comb.flatten() - translation_vector_true)
            < 1.0
        )
