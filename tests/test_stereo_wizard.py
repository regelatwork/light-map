import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.calibration.wizard import StereoCalibrationWizard
from light_map.vision.infrastructure.camera import Camera


@pytest.fixture
def mock_tokens(tmp_path):
    tokens_path = tmp_path / "tokens.json"
    content = {
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
                "name": "PPI 1",
                "type": "Ruler",
                "profile": "pc",
                "size": None,
                "height_mm": None,
                "color": None,
            },
            "41": {
                "name": "PPI 2",
                "type": "Ruler",
                "profile": "pc",
                "size": None,
                "height_mm": None,
                "color": None,
            },
            "42": {
                "name": "Arena 1",
                "type": "Arena",
                "profile": "pc",
                "size": None,
                "height_mm": None,
                "color": None,
            },
        },
    }
    with open(tokens_path, "w") as f:
        json.dump(content, f)
    return str(tokens_path)


@pytest.fixture
def wizard(mock_tokens):
    return StereoCalibrationWizard(tokens_path=mock_tokens)


@pytest.fixture
def mock_camera():
    cam = MagicMock(spec=Camera)
    cam.id = "cam_1"
    cam.read.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    return cam


def test_wizard_resolve_intrinsics(wizard):
    with (
        patch("os.path.exists", return_value=True),
        patch(
            "light_map.calibration.wizard.np.load",
            return_value={"K": np.eye(3), "dist": np.zeros(5)},
        ),
    ):
        wizard.resolve_lens_intrinsics("cam_left", "cam_right")
        assert wizard.camera_left_intrinsics is not None
        assert wizard.camera_right_intrinsics is not None


def test_wizard_get_valid_tokens(wizard):
    tokens = wizard.get_valid_tokens()
    assert 0 in tokens
    assert 40 in tokens
    assert 41 in tokens
    assert 42 in tokens
    assert tokens[0] == 50.0

    @patch("light_map.calibration.wizard.compute_projector_homography")
    @patch("light_map.calibration.wizard.calculate_ppi_from_frame")
    @patch("light_map.calibration.wizard.calibrate_extrinsics")
    @patch("light_map.calibration.wizard.StereoCalibrationWizard.save_calibration")
    def test_run_calibration_success(
        mock_save, mock_calibrate, mock_ppi, mock_homo, wizard, mock_camera
    ):
        # Setup mocks
        mock_homo.return_value = np.eye(3)
        mock_ppi.return_value = 100.0
        mock_calibrate.return_value = (np.eye(3), np.zeros(3), np.eye(3), np.zeros(3), 0.1)

        # Add grid corners to wizard (mocking Phase 1 return)
        wizard.grid_corners_world = np.array([[0, 0, 0], [100, 100, 0]])

        # We need to mock _detect_markers to return 40 and 41
        with (
            patch.object(
                wizard,
                "_detect_markers",
                return_value=(np.zeros((5, 4, 2)), np.array([40, 41]), None),
            ),
            patch("os.path.exists", return_value=True),
            patch(
                "light_map.calibration.wizard.np.load",
                return_value={"K": np.eye(3), "dist": np.zeros(5)},
            ),
        ):
            result = wizard.run_calibration(mock_camera, mock_camera)

            assert result["status"] == "success"
            assert "left" in result
            assert "right" in result
            mock_save.assert_called_once()


def test_wizard_discover_cameras(wizard):
    # Case 1: tx > 0 (camera_left is right)
    r_l = np.eye(3)
    t_l = np.array([10.0, 0.0, 0.0])
    r_r = np.eye(3)
    t_r = np.array([-10.0, 0.0, 0.0])

    cam_l = MagicMock(spec=Camera)
    cam_l.id = "left_id"
    cam_r = MagicMock(spec=Camera)
    cam_r.id = "right_id"

    left, right = wizard._discover_cameras(r_l, t_l, r_r, t_r, cam_l, cam_r)
    assert left == "right_id"
    assert right == "left_id"

    # Case 2: tx < 0 (camera_left is left)
    t_l_neg = np.array([-10.0, 0.0, 0.0])
    left_neg, right_neg = wizard._discover_cameras(r_l, t_l_neg, r_r, t_r, cam_l, cam_r)
    assert left_neg == "left_id"
    assert right_neg == "right_id"
