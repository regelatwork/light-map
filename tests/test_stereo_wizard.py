import unittest
import numpy as np
import os
import json
from unittest.mock import MagicMock, patch
from light_map.calibration.wizard import StereoCalibrationWizard

class TestStereoCalibrationWizard(unittest.TestCase):
    def setUp(self):
        self.tokens_path = "test_tokens.json"
        self.test_tokens = {
            "token_profiles": {
                "pc": {"size": 1, "height_mm": 50.0},
                "small": {"size": 1, "height_mm": 15.0}
            },
            "aruco_defaults": {
                "0": {"name": "Token 0", "type": "PC", "profile": "pc"},
                "1": {"name": "Token 1", "type": "PC", "profile": "pc"},
                "40": {"name": "Ruler 1", "type": "Ruler", "profile": "large"},
                "41": {"name": "Ruler 2", "type": "Ruler", "profile": "large"},
                "42": {"name": "Arena 1", "type": "Arena", "profile": "medium"},
            }
        }
        with open(self.tokens_path, "w") as f:
            json.dump(self.test_tokens, f)
        self.wizard = StereoCalibrationWizard(self.tokens_path)

    def tearDown(self):
        if os.path.exists(self.tokens_path):
            os.remove(self.tokens_path)

    def test_get_valid_tokens(self):
        valid_tokens = self.wizard.get_valid_tokens()
        # ID 0 and 1 should be valid (pc profile height 50.0 > 0)
        self.assertIn(0, valid_tokens)
        self.assertIn(1, valid_tokens)
        # ID 40 and 41 should be excluded (out of range 0-39)
        self.assertNotIn(40, valid_tokens)
        self.assertNotIn(41, valid_tokens)
        # ID 42 should be excluded (out of range 0-39)
        self.assertNotIn(42, valid_tokens)

    @patch("light_map.calibration.wizard.np.load")
    @patch("os.path.exists")
    def test_resolve_lens_intrinsics_success(self, mock_exists, mock_load):
        mock_exists.side_effect = lambda p: "calibration" in p
        mock_data = {"K": np.eye(3), "dist": np.zeros(5)}
        mock_load.return_value = mock_data
        
        self.wizard.resolve_lens_intrinsics("camera_left", "camera_right")
        
        np.testing.assert_array_equal(self.wizard.camera_left_intrinsics, mock_data["K"])
        np.testing.assert_array_equal(self.wizard.camera_right_intrinsics, mock_data["K"])

    @patch("light_map.calibration.wizard.np.load")
    @patch("os.path.exists")
    def test_resolve_lens_intrinsics_fallback(self, mock_exists, mock_load):
        # camera_left_calibration.npz does not exist, but camera_calibration.npz does
        def exists_side_effect(p):
            return p == "camera_calibration.npz"
        mock_exists.side_effect = exists_side_effect
        
        mock_data = {"K": np.eye(3), "dist": np.zeros(5)}
        mock_load.return_value = mock_data
        
        self.wizard.resolve_lens_intrinsics("camera_left", "camera_right")
        
        np.testing.assert_array_equal(self.wizard.camera_left_intrinsics, mock_data["K"])
        np.testing.assert_array_equal(self.wizard.camera_right_intrinsics, mock_data["K"])

if __name__ == "__main__":
    unittest.main()
