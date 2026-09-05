import cv2
import numpy as np
import pytest

from light_map.calibration.calibration_logic import calibrate_extrinsics


def test_calibrate_extrinsics_synthetic():
    # Setup Camera Intrinsics
    camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # Setup Pose (R, t)
    # Rotation: zero
    rotation_vector_true = np.array([0, 0, 0], dtype=np.float32)
    # Translation: (0, 0, 500)
    translation_vector_true = np.array([0, 0, 500], dtype=np.float32)

    # Setup World Points (X, Y, Z in mm)
    # 4 points at Z=25 (tokens)
    ppi = 100.0

    # Projector Coordinates for tokens (Centers)
    # These are in pixels.
    projector_coords_px = [[100, 100], [200, 100], [100, 200], [200, 200]]
    known_targets = {1: (100, 100), 2: (200, 100), 3: (100, 200), 4: (200, 200)}
    token_heights = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}
    token_sizes = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

    # Generate object_points in Table space (mm)
    # Convert pixel coordinates to mm using ppi
    # mm = pixels * (25.4 / ppi)
    object_points = []
    for i, (px_c, py_c) in enumerate(projector_coords_px):
        size_px = token_sizes[i + 1] * ppi
        px_mm = px_c * (25.4 / ppi)
        py_mm = py_c * (25.4 / ppi)

        offsets_px = [
            [-size_px / 2, -size_px / 2],
            [size_px / 2, -size_px / 2],
            [size_px / 2, size_px / 2],
            [-size_px / 2, size_px / 2],
        ]
        for dx_px, dy_px in offsets_px:
            dx_mm = dx_px * (25.4 / ppi)
            dy_mm = dy_px * (25.4 / ppi)
            object_points.append([px_mm + dx_mm, py_mm + dy_mm, 25.0])

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
                for i in range(4):
                    corners.append(image_points[i * 4 : (i + 1) * 4].reshape(1, 4, 2))
                ids = np.array([[1], [2], [3], [4]], dtype=np.int32)
                return corners, ids, []

        mp.setattr(cv2.aruco, "ArucoDetector", lambda *args: MockDetector())
        mp.setattr(cv2, "cvtColor", lambda frame, *args: frame)

        # We use an identity homography (Table space == Projector space)
        projector_matrix = np.eye(3, dtype=np.float32)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Test 1: Only Tokens (Z > 0) with known_targets
        result = calibrate_extrinsics(
            frame,
            projector_matrix,
            camera_matrix,
            distortion_coefficients,
            ppi,
            token_heights,
            known_targets=known_targets,
            token_sizes=token_sizes,
            aruco_ids=np.array([1, 2, 3, 4]),
            aruco_corners=(
                np.array([[[10, 10], [20, 10], [20, 20], [10, 20]]]),
                np.array([[[30, 30], [40, 30], [40, 40], [30, 40]]]),
                np.array([[[50, 50], [60, 50], [60, 60], [50, 60]]]),
                np.array([[[70, 70], [80, 70], [80, 80], [70, 80]]]),
            ),
        )

        assert result is not None
        rotation_vector_res, translation_vector_res, _, _ = result
        assert rotation_vector_diff(rotation_vector_res, rotation_vector_true) < 0.1
        assert np.linalg.norm(translation_vector_res.flatten() - translation_vector_true) < 5.0

        # Test 2: Combined (Ground + Tokens) with known_targets
        # Ground points are at Z=0
        ground_points_3d = np.array(projector_coords_px, dtype=np.float32)
        ground_points_3d[:, 2] = 0
        # Convert pixel coordinates to mm for ground points as well
        ground_points_3d *= 25.4 / ppi

        image_points_ground, _ = cv2.projectPoints(
            ground_points_3d,
            rotation_vector_true,
            translation_vector_true,
            camera_matrix,
            distortion_coefficients,
        )
        image_points_ground = image_points_ground.reshape(-1, 2)

        result_combined = calibrate_extrinsics(
            frame,
            projector_matrix,
            camera_matrix,
            distortion_coefficients,
            ppi,
            token_heights,
            ground_points_camera=image_points_ground,
            ground_points_projector=np.array(projector_coords_px, dtype=np.float32).reshape(-1, 2),
            known_targets=known_targets,
            token_sizes=token_sizes,
            aruco_ids=np.array([1, 2, 3, 4]),
            aruco_corners=(
                np.array([[[10, 10], [20, 10], [20, 20], [10, 20]]]),
                np.array([[[30, 30], [40, 30], [40, 40], [30, 40]]]),
                np.array([[[50, 50], [60, 50], [60, 60], [50, 60]]]),
                np.array([[[70, 70], [80, 70], [80, 80], [70, 80]]]),
            ),
        )

        assert result_combined is not None
        rotation_vector_comb, translation_vector_comb, _, _ = result_combined
        assert rotation_vector_diff(rotation_vector_comb, rotation_vector_true) < 0.05
        assert np.linalg.norm(translation_vector_comb.flatten() - translation_vector_true) < 1.0
