"""
Test suite for StereoCalibrationWizard.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.calibration.wizard import StereoCalibrationWizard


@pytest.fixture
def mock_wizard(tmp_path):
    tokens_path = str(tmp_path / "tokens.json")
    # Create dummy tokens.json
    with open(tokens_path, "w") as f:
        f.write(
            '{"token_profiles": {"pc": {"height_mm": 50.0}}, "aruco_defaults": {"0": {"profile": "pc", "height_mm": 50.0}, "1": {"profile": "pc", "height_mm": 50.0}, "2": {"profile": "pc", "height_mm": 50.0}, "3": {"profile": "pc", "height_mm": 50.0}, "40": {"profile": "pc", "height_mm": 50.0}, "41": {"profile": "pc", "height_mm": 50.0}, "5": {"profile": "pc", "height_mm": 50.0}, "43": {"profile": "pc", "height_mm": 50.0}, "44": {"profile": "pc", "height_mm": 50.0}, "45": {"profile": "pc", "height_mm": 50.0}, "46": {"profile": "pc", "height_mm": 50.0}, "47": {"profile": "pc", "height_mm": 50.0}, "48": {"profile": "pc", "height_mm": 50.0}, "49": {"profile": "pc", "height_mm": 50.0}}}'
        )

    with patch("light_map.calibration.wizard.load_intrinsics") as mock_load:
        mock_load.return_value = (np.eye(3), np.zeros(5))

        wizard = StereoCalibrationWizard(tokens_path, str(tmp_path))

        # Mock detector
        wizard.marker_detector.detect = MagicMock(
            return_value=[
                (40, np.array([[0, 0], [1, 1]])),
                (41, np.array([[2, 2], [3, 3]])),
                (0, np.array([[4, 4], [5, 5]])),
                (1, np.array([[6, 6], [7, 7]])),
                (2, np.array([[8, 8], [9, 9]])),
                (3, np.array([[10, 10], [11, 11]])),
                (5, np.array([[12, 12], [13, 13]])),
                (43, np.array([[14, 14], [15, 15]])),
                (44, np.array([[16, 16], [17, 17]])),
                (45, np.array([[18, 18], [19, 19]])),
                (46, np.array([[20, 20], [21, 21]])),
                (47, np.array([[22, 22], [23, 23]])),
                (48, np.array([[24, 24], [25, 25]])),
                (49, np.array([[26, 26], [27, 27]])),
            ]
        )

        # Mock solver
        wizard.solver = MagicMock()
        wizard.solver.r_stereo = np.eye(3)
        wizard.solver.t_stereo = np.array([0.128, 0, 0])
        wizard.solver.camera_left_extrinsics = np.eye(3)
        wizard.solver.camera_left_t = np.zeros(3)
        wizard.solver.camera_right_extrinsics = np.eye(3)
        wizard.solver.camera_right_t = np.zeros(3)
        wizard.solver.grid_corners_3d = np.array(
            [
                [0, 0, 0],
                [1, 1, 1],
                [2, 2, 2],
                [3, 3, 3],
                [4, 4, 4],
                [5, 5, 5],
                [6, 6, 6],
                [7, 7, 7],
                [8, 8, 8],
                [9, 9, 9],
                [10, 10, 10],
                [11, 11, 11],
            ]
        )
        wizard.solver.solve_phase3_auto_discovery.return_value = ("camera_0", "camera_1")

        yield wizard


def test_wizard_run_calibration(mock_wizard):
    left_img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    right_img = np.zeros((1080, 1920, 3), dtype=np.uint8)

    result = mock_wizard.run_calibration(left_img, right_img)

    assert "roi_left" in result
    assert "roi_right" in result
    assert "r_stereo" in result
    assert "t_stereo" in result
    assert "left_id" in result
    assert "right_id" in result
    assert np.array_equal(result["r_stereo"], np.eye(3))
    assert np.array_equal(result["t_stereo"], np.array([0.128, 0, 0]))
