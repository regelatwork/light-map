import json
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from light_map.calibration.wizard import StereoCalibrationWizard


class TestStereoCalibrationWizard(unittest.TestCase):
    def setUp(self):
        # Mock tokens.json
        self.tokens_data = {
            "token_profiles": {"pc": {"size": 1, "height_mm": 50.0}},
            "aruco_defaults": {
                "0": {
                    "name": "Token 0",
                    "type": "PC",
                    "profile": "pc",
                    "size": None,
                    "height_mm": None,
                    "color": None,
                },
                "40": {
                    "name": "Ruler 1",
                    "type": "Ruler",
                    "profile": "large",
                    "size": None,
                    "height_mm": None,
                    "color": None,
                },
                "41": {
                    "name": "Ruler 2",
                    "type": "Ruler",
                    "profile": "large",
                    "size": None,
                    "height_mm": None,
                    "color": None,
                },
                "42": {
                    "name": "Arena 2",
                    "type": "Arena",
                    "profile": "medium",
                    "size": None,
                    "height_mm": None,
                    "color": None,
                },
            },
        }
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=json.dumps(self.tokens_data))
        ):
            with patch("os.path.exists", return_value=True):
                self.wizard = StereoCalibrationWizard(tokens_path="fake_path.json")

        # Set some internal state
        self.wizard.camera_left_intrinsics = np.eye(3)
        self.wizard.camera_right_intrinsics = np.eye(3)
        self.wizard.camera_left_dist = np.zeros(5)
        self.wizard.camera_right_dist = np.zeros(5)
        self.wizard.ppi = 100.0
        # Mock grid_corners_world (6 points in a 2x4 grid)
        # Each point is (x, y, z) in mm
        self.wizard.grid_corners_world = np.array(
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
        valid_tokens = self.wizard.get_valid_tokens()
        self.assertIn(0, valid_tokens)
        self.assertEqual(valid_tokens[0]["height"], 50.0)
        self.assertEqual(valid_tokens[0]["size"], 1.0)

        # Marker 40 should not be in valid_tokens (IDs 0-39 only)
        self.assertNotIn(40, valid_tokens)

    def test_discover_cameras_success(self):
        # Mock camera objects
        cam_l = MagicMock()
        cam_l.id = "left_id"
        cam_r = MagicMock()
        cam_r.id = "right_id"

        # Case 1: tx > 0 (camera_left is on the right)
        # Use a small rotation (approx 1 degree)
        r_l = np.array([[0.9998, -0.0174, 0], [0.0174, 0.9998, 0], [0, 0, 1]], dtype=np.float32)
        t_l = np.array([10.0, 0.0, 0.0], dtype=np.float32)  # tx > 0
        r_r = np.eye(3, dtype=np.float32)
        t_r = np.array([0.0, 0.0, 0.0], dtype=np.float32)


        left_id, right_id = self.wizard._discover_cameras(r_l, t_l, r_r, t_r, cam_l, cam_r)
        self.assertEqual(left_id, "right_id")
        self.assertEqual(right_id, "left_id")

        # Case 2: tx < 0 (camera_left is on the left)
        t_l = np.array([-10.0, 0.0, 0.0], dtype=np.float32)  # tx < 0
        left_id, right_id = self.wizard._discover_cameras(r_l, t_l, r_r, t_r, cam_l, cam_r)
        self.assertEqual(left_id, "left_id")
        self.assertEqual(right_id, "right_id")

    def test_discover_cameras_rotation_fail(self):
        cam_l = MagicMock()
        cam_l.id = "left_id"
        cam_r = MagicMock()
        cam_r.id = "right_id"

        # Large rotation
        r_l = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float32)  # 90 degree rotation
        t_l = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        r_r = np.eye(3, dtype=np.float32)
        t_r = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        with self.assertRaises(RuntimeError):
            self.wizard._discover_cameras(r_l, t_l, r_r, t_r, cam_l, cam_r)

    def test_compute_roi(self):
        # Setup: r_l, t_l, r_r, t_r are identity
        r_l = np.eye(3, dtype=np.float32)
        t_l = np.zeros(3, dtype=np.float32)
        r_r = np.eye(3, dtype=np.float32)
        t_r = np.zeros(3, dtype=np.float32)
        k_l = np.eye(3, dtype=np.float32)
        k_r = np.eye(3, dtype=np.float32)
        dist_l = np.zeros(5, dtype=np.float32)
        dist_r = np.zeros(5, dtype=np.float32)

        # Create dummy frame_l (e.g., 1920x1080)
        frame_l = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Mock find_checkerboard_corners to return some points
        # Let's say the points are in the middle of the image
        # Since r,t,k are identity, the points in tabletop (grid_corners_world)
        # will project directly to the same pixel coordinates.
        # Bounding box of grid_corners_world: min=(0,0), max=(120,40)
        # With margin 5% of (120, 40) is (6, 2)
        # ROI should be (-6, -2, 126, 42) clipped to (0,0,1920,1080)
        # So (0, 0, 126, 42)

        with patch.object(self.wizard, "_find_checkerboard_corners") as mock_find:
            # mock_find returns the grid corners as they appear in the camera
            # Since r,t,k are identity, they appear at the same pixel locations as mm locations
            mock_find.return_value = np.array(self.wizard.grid_corners_world, dtype=np.float32)

            roi_l, roi_r = self.wizard._compute_roi(
                frame_l, r_l, t_l, r_r, t_r, k_l, k_r, dist_l, dist_r, self.wizard.ppi
            )

            # Expected: min_x=0, max_x=120, min_y=0, max_y=40
            # Width=120, Height=40. MarginX=6, MarginY=2
            # ROI: [0-6, 0-2, 120+6, 40+2] -> [-6, -2, 126, 42] -> [0, 0, 126, 42]
            self.assertTrue(np.array_equal(roi_l, np.array([0, 0, 126, 42])))
            self.assertTrue(np.array_equal(roi_r, np.array([0, 0, 126, 42])))


if __name__ == "__main__":
    unittest.main()
