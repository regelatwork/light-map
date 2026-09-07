import json
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from light_map.calibration.wizard import StereoCalibrationWizard


class TestStereoCalibrationWizard(unittest.TestCase):
    def setUp(self):
        self.tokens_data = {
            "token_profiles": {
                "pc": {"size": 1, "height_mm": 50.0},
                "small": {"size": 1, "height_mm": 15.0},
                "huge": {"size": 3, "height_mm": 60.0},
                "invalid": {"size": 1, "height_mm": -1.0},
            },
            "aruco_defaults": {
                "0": {"name": "Token 0", "type": "PC", "profile": "pc"},
                "1": {"name": "Token 1", "type": "PC", "profile": "pc"},
                "40": {"name": "Ruler 1", "type": "Ruler", "profile": "large"},
                "41": {"name": "Ruler 2", "type": "Ruler", "profile": "large"},
                "5": {"name": "Arena 2", "type": "Arena", "profile": "medium"},
            },
        }
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=json.dumps(self.tokens_data))
        ):
            with patch("os.path.exists", return_value=True):
                with patch("numpy.load") as mock_load:
                    mock_load.return_value = {"K": np.eye(3), "dist": np.zeros(5)}
                    with patch(
                        "light_map.calibration.wizard.load_intrinsics",
                        return_value=(np.eye(3), np.zeros(5)),
                    ):
                        self.wizard = StereoCalibrationWizard(
                            tokens_path="fake_path.json", base_path="fake_base_path"
                        )

        # Set some internal state
        self.wizard.k_left = np.eye(3)
        self.wizard.k_right = np.eye(3)
        self.wizard.dist_left = np.zeros(5)
        self.wizard.dist_right = np.zeros(5)
        self.wizard.projector_ppi = 100.0
        # Mock grid_corners_world (8 points in a 2x4 grid)
        self.wizard.solver.grid_corners_3d = np.array(
            [
                [0, 0, 0],
                [40, 0, 0],
                [80, 0, 0],
                [120, 0, 0],
                [0, 40, 0],
                [40, 40, 0],
                [80, 40, 0],
                [120, 40, 0],
            ],
            dtype=np.float32,
        )

    def test_get_valid_tokens(self):
        # Mock the token data to ensure it filters correctly
        # The TokenManager will be called with range(40)
        valid_tokens = self.wizard.token_manager.get_candidate_tokens(range(40))
        self.assertTrue(any(t.id == "0" for t in valid_tokens))
        self.assertTrue(any(t.id == "1" for t in valid_tokens))
        # Token 40 is not in range(40)
        self.assertFalse(any(t.id == "40" for t in valid_tokens))

    def test_discover_cameras_positive_tx(self):
        # Case 1: tx > 0 (camera_left is on the right)
        r_l = np.eye(3, dtype=np.float32)
        t_l = np.array([10.0, 0.0, 0.0], dtype=np.float32)  # Positive tx
        r_r = np.eye(3, dtype=np.float32)

        self.wizard.solver.camera_left_extrinsics = r_l
        self.wizard.solver.camera_left_t = t_l
        self.wizard.solver.camera_right_extrinsics = r_r
        self.wizard.solver.camera_right_t = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.wizard.solver.r_stereo = r_l
        self.wizard.solver.t_stereo = t_l

        left_id, right_id = self.wizard.solver.solve_phase3_auto_discovery()

        self.assertEqual(left_id, "camera_0")
        self.assertEqual(right_id, "camera_1")

    def test_discover_cameras_negative_tx(self):
        r_l = np.eye(3, dtype=np.float32)
        t_l = np.array([-10.0, 0.0, 0.0], dtype=np.float32)  # Negative tx
        r_r = np.eye(3, dtype=np.float32)

        self.wizard.solver.camera_left_extrinsics = r_l
        self.wizard.solver.camera_left_t = t_l
        self.wizard.solver.camera_right_extrinsics = r_r
        self.wizard.solver.camera_right_t = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.wizard.solver.r_stereo = r_l
        self.wizard.solver.t_stereo = t_l

        left_id, right_id = self.wizard.solver.solve_phase3_auto_discovery()

        self.assertEqual(left_id, "camera_1")
        self.assertEqual(right_id, "camera_0")

    def test_discover_cameras_rotation_verification(self):
        # Test rotation verification failure
        r_l = np.eye(3, dtype=np.float32)
        # Create a rotation vector for 20 degrees around Z axis
        angle = np.radians(20)
        r_r = np.array(
            [
                [np.cos(angle), -np.sin(angle), 0.0],
                [np.sin(angle), np.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

        t_l = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        t_r = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        self.wizard.solver.camera_left_extrinsics = r_l
        self.wizard.solver.camera_left_t = t_l
        self.wizard.solver.camera_right_extrinsics = r_r
        self.wizard.solver.camera_right_t = t_r
        self.wizard.solver.r_stereo = r_r
        self.wizard.solver.t_stereo = t_l

        with self.assertRaises(RuntimeError) as cm:
            self.wizard.solver.solve_phase3_auto_discovery()

        self.assertIn("Significant rotation detected", str(cm.exception))

    def test_verify_triangulation_accuracy(self):
        # This test verifies that triangulated 3D positions match physical measurements
        # within ±2.0mm error across the tabletop area.
        # Geometry: cameras mounted at height Z_cam = 1000mm looking down at table (Z_world = 0).
        # Camera optical axis points in -Z_world: R_down = diag(1, -1, -1).
        R_down = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]], dtype=np.float32)
        t_l = np.array([0.0, 0.0, 1000.0], dtype=np.float32)
        t_r = np.array([-128.0, 0.0, 1000.0], dtype=np.float32)

        K_l = np.array([[800.0, 0, 960.0], [0, 800.0, 540.0], [0, 0, 1.0]], dtype=np.float32)
        dist_l = np.zeros(5, dtype=np.float32)
        K_r = np.array([[800.0, 0, 960.0], [0, 800.0, 540.0], [0, 0, 1.0]], dtype=np.float32)
        dist_r = np.zeros(5, dtype=np.float32)

        # Projection matrices: P = K @ [R | t]
        P_l = K_l @ np.hstack([R_down, t_l.reshape(3, 1)])
        P_r = K_r @ np.hstack([R_down, t_r.reshape(3, 1)])

        # World points: table corners (Z=0) and elevated tokens (Z=25mm, Z=50mm)
        world_pts = np.array(
            [
                [0.0, 0.0, 0.0],
                [150.0, 100.0, 0.0],
                [-150.0, -100.0, 25.0],
                [100.0, -80.0, 50.0],
            ],
            dtype=np.float32,
        )

        pts_l_proj, _ = cv2.projectPoints(world_pts, R_down, t_l, K_l, dist_l)
        pts_r_proj, _ = cv2.projectPoints(world_pts, R_down, t_r, K_r, dist_r)
        pts_l_2d = pts_l_proj.reshape(-1, 2)
        pts_r_2d = pts_r_proj.reshape(-1, 2)

        # Tier 1: Deterministic Zero-Noise Triangulation Verification
        pts_4d_zero = cv2.triangulatePoints(P_l, P_r, pts_l_2d.T, pts_r_2d.T)
        triangulated_zero = (pts_4d_zero[:3] / pts_4d_zero[3]).T
        for i in range(len(world_pts)):
            dist_zero = np.linalg.norm(triangulated_zero[i] - world_pts[i])
            self.assertLess(dist_zero, 0.01)

        # Tier 2: Subpixel Refinement Noise (sigma = 0.05 px, locked seed)
        rng = np.random.default_rng(42)
        noise_l = rng.normal(0, 0.05, pts_l_2d.shape).astype(np.float32)
        noise_r = rng.normal(0, 0.05, pts_r_2d.shape).astype(np.float32)
        pts_l_noisy = pts_l_2d + noise_l
        pts_r_noisy = pts_r_2d + noise_r

        pts_4d_noisy = cv2.triangulatePoints(P_l, P_r, pts_l_noisy.T, pts_r_noisy.T)
        triangulated_noisy = (pts_4d_noisy[:3] / pts_4d_noisy[3]).T
        for i in range(len(world_pts)):
            dist_noisy = np.linalg.norm(triangulated_noisy[i] - world_pts[i])
            self.assertLess(dist_noisy, 2.0)

    def test_compute_roi(self):
        R_down = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]], dtype=np.float32)
        t_l = np.array([0.0, 0.0, 1000.0], dtype=np.float32)
        t_r = np.array([-128.0, 0.0, 1000.0], dtype=np.float32)
        K = np.array([[800.0, 0, 960.0], [0, 800.0, 540.0], [0, 0, 1.0]], dtype=np.float32)

        corners_3d = np.array(
            [
                [-300.0, -200.0, 0.0],
                [300.0, -200.0, 0.0],
                [300.0, 200.0, 0.0],
                [-300.0, 200.0, 0.0],
            ],
            dtype=np.float32,
        )

        from light_map.calibration.roi_calculator import compute_roi_pass2

        roi_l, roi_r = compute_roi_pass2(
            (1080, 1920),
            R_down,
            t_l,
            R_down,
            t_r,
            max_height_mm=200.0,
            corners_3d=corners_3d,
            k_left=K,
            k_right=K,
        )

        self.assertIsInstance(roi_l, tuple)
        self.assertEqual(len(roi_l), 4)
        self.assertIsInstance(roi_r, tuple)
        self.assertEqual(len(roi_r), 4)

        for roi in (roi_l, roi_r):
            x, y, w, h = roi
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, 1920)
            self.assertLessEqual(y + h, 1080)
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)


if __name__ == "__main__":
    unittest.main()
