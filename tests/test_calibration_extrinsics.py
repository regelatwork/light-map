import cv2
import numpy as np
import pytest

from light_map.calibration.calibration_logic import calibrate_extrinsics


def test_calibrate_extrinsics_synthetic():
    # Setup Camera Intrinsics
    camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
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

    # Projector Coordinates for tokens (Centers)
    projector_coords = [[100, 100], [500, 100], [100, 400], [500, 400]]
    known_targets = {1: (100, 100), 2: (500, 100), 3: (100, 400), 4: (500, 400)}
    token_heights = {1: 25.0, 2: 25.0, 3: 25.0, 4: 25.0}
    token_sizes = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}

    # Replicate calibrate_extrinsics logic to generate object_points (Corners)
    object_points = []
    for i, (px_c, py_c) in enumerate(projector_coords):
        size_px = token_sizes[i + 1] * ppi
        offsets = [
            [-size_px / 2, -size_px / 2],
            [size_px / 2, -size_px / 2],
            [size_px / 2, size_px / 2],
            [-size_px / 2, size_px / 2],
        ]
        for dx, dy in offsets:
            wx = (px_c + dx) / ppi_mm
            wy = (py_c + dy) / ppi_mm
            object_points.append([wx, wy, 25.0])

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
                # We need to provide 4 sets of 4 corners (16 points total)
                # because each token has 4 corners.
                # These corners should match the ones that calibrate_extrinsics
                # would calculate from known_targets.
                # In our test, they are the 4 corners of each token.

                # Wait, the test expects 4 tokens.
                # We can just return 16 corners.
                # But the test expects 4 IDs.

                # Let's just return the 4 sets of corners.
                # Each set of 4 corners is for one token.
                # Since we have 16 points total, we'll divide them into 4 groups of 4.

                # Wait, we need to return the corners for the IDs.
                # Let's just return the 4 corners for each of the 4 tokens.

                # We'll just mock the corners to be the image_points.
                # Since we have 16 points, we'll take 4 at a time.

                # Wait, we need to return the corners for the IDs.
                # Let's just return the 4 corners for each of the 4 tokens.

                # We'll just mock the corners to be the image_points.
                # Since we have 16 points, we'll take 4 at a time.

                corners = []
                for i in range(4):
                    corners.append(image_points[i * 4 : (i + 1) * 4].reshape(1, 4, 2))

                ids = np.array([[1], [2], [3], [4]], dtype=np.int32)
                return corners, ids, []

        mp.setattr(cv2.aruco, "ArucoDetector", lambda *args: MockDetector())
        mp.setattr(cv2, "cvtColor", lambda frame, *args: frame)

        # Ground Points (Z=0)
        # The centers of the 4 tokens.
        # Since the corners are symmetric around the center, the average of the 4 corners is the center.
        # We'll use the 4 points from the centers.
        # Wait, we need 4 points.
        # Let's just use the 4 points from the centers.
        # We can calculate the centers from the corners.
        # Since the corners are symmetric, the average of the 4 corners is the center.

        centers_3d = []
        for i in range(4):
            # image_points[i*4 : (i+1)*4] are the 4 corners of token i.
            # We need their 3D positions.
            # We can get them from the object_points.
            # object_points[i*4 : (i+1)*4] are the 4 corners of token i.
            # The average is the center.
            centers_3d.append(np.mean(object_points[i * 4 : (i + 1) * 4], axis=0))

        centers_3d = np.array(centers_3d, dtype=np.float32)
        ground_points_3d = centers_3d.copy()
        ground_points_3d[:, 2] = 0

        image_points_ground, _ = cv2.projectPoints(
            ground_points_3d,
            rotation_vector_true,
            translation_vector_true,
            camera_matrix,
            distortion_coefficients,
        )
        image_points_ground = image_points_ground.reshape(-1, 2)

        projector_matrix, _ = cv2.findHomography(
            image_points_ground, np.array(projector_coords, dtype=np.float32).reshape(-1, 2)
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Test 1: Only Tokens (Z > 0) with known_targets
        # In this path, we provide known_targets.
        # We also provide aruco_corners.
        # They should be consistent.
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
        result_combined = calibrate_extrinsics(
            frame,
            projector_matrix,
            camera_matrix,
            distortion_coefficients,
            token_heights,
            ppi,
            ground_points_camera=image_points_ground,
            ground_points_projector=np.array(projector_coords, dtype=np.float32).reshape(-1, 2),
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
