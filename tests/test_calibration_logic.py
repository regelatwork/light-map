import json
import os
import tempfile
import unittest

import numpy as np

from light_map.calibration.calibration_logic import (
    calculate_ppi_from_frame,
    filter_candidate_tokens,
    resolve_lens_intrinsics,
    solve_joint_extrinsics,
)


class TestCalibrationLogic(unittest.TestCase):
    def test_filter_candidate_tokens(self):
        path = tempfile.mkdtemp()
        data = {
            "token_profiles": {"pc": {"size": 1, "height_mm": 50.0}},
            "aruco_defaults": {
                str(i): {"name": f"Token {i}", "type": "PC", "profile": "pc", "height_mm": 10.0}
                for i in range(8)
            },
        }
        with open(os.path.join(path, "tokens.json"), "w") as f:
            json.dump(data, f)

        tokens_path = os.path.join(path, "tokens.json")
        candidates = filter_candidate_tokens(tokens_path)
        self.assertEqual(len(candidates), 8)
        for c in candidates:
            self.assertGreater(c["height_mm"], 0)

    def test_resolve_lens_intrinsics_fail(self):
        with self.assertRaises(FileNotFoundError):
            resolve_lens_intrinsics("unknown")

    def test_calculate_ppi_from_frame_basic(self):
        # Mock projector matrix (Identity for simplicity)
        # Note: cv2.perspectiveTransform expects a 3x4 matrix
        proj_matrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float32)
        # Mock frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock aruco_ids and corners
        # We need to make sure the corners are in the correct format (1, 4, 2)
        aruco_ids = np.array([40, 41])
        aruco_corners = (
            np.array([[[10, 10], [20, 10], [20, 20], [10, 20]]], dtype=np.float32),  # ID 40
            np.array([[[30, 30], [40, 30], [40, 40], [30, 40]]], dtype=np.float32),  # ID 41
        )

        # p1_cam = [10, 10], p2_cam = [30, 30]
        # pts_proj = p1_cam, p2_cam (since proj_matrix is identity)
        # dist_px = sqrt(20^2 + 20^2) = 28.284
        # dist_inches = 100 / 25.4 = 3.937
        # ppi = 28.284 / 3.937 = 7.18
        ppi = calculate_ppi_from_frame(
            frame,
            proj_matrix,
            target_dist_mm=100.0,
            aruco_corners=aruco_corners,
            aruco_ids=aruco_ids,
        )
        self.assertAlmostEqual(ppi, 7.18, places=2)

    def test_solve_joint_extrinsics_insufficient_points(self):
        # Should return None if not enough points
        res = solve_joint_extrinsics(
            np.zeros((480, 640, 3)),
            np.zeros((480, 640, 3)),
            np.eye(3, 4).astype(np.float32),
            np.eye(3, 4).astype(np.float32),
            np.eye(3, 4).astype(np.float32),
            np.eye(3, 4).astype(np.float32),
            np.eye(3, 4).astype(np.float32),
            {1: 10.0, 2: 20.0},
            100.0,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
