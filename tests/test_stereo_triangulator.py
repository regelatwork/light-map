import cv2
import numpy as np
import pytest

from light_map.core.common_types import DetectionResult, ResultType
from light_map.core.stereo_triangulator import StereoTriangulator


@pytest.fixture
def triangulator():
    # Downward-looking stereo rig:
    # Left camera at (0, 0, 1000), Right camera at (128, 0, 1000)
    R_down = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]], dtype=np.float32)
    t_l = np.array([0.0, 0.0, 1000.0], dtype=np.float32)
    t_r = np.array([-128.0, 0.0, 1000.0], dtype=np.float32)

    K = np.array([[800.0, 0, 960.0], [0, 800.0, 540.0], [0, 0, 1.0]], dtype=np.float32)
    dist = np.zeros(5, dtype=np.float32)

    return StereoTriangulator(
        camera_left_intrinsics=K,
        camera_left_dist=dist,
        camera_right_intrinsics=K,
        camera_right_dist=dist,
        rotation_left=R_down,
        translation_left=t_l,
        rotation_right=R_down,
        translation_right=t_r,
        roi_left=[0, 0, 1920, 1080],
        roi_right=[0, 0, 1920, 1080],
        frame_time=0.033,  # 30 fps
        max_allowed_skew=0.05,
    )


def test_stereo_triangulator_matched_pair(triangulator):
    # World ground truth point at (150, 100, 50) mm
    P_world = np.array([[150.0, 100.0, 50.0]], dtype=np.float32)

    pts_l, _ = cv2.projectPoints(
        P_world, triangulator.R_L, triangulator.t_L, triangulator.K_L, triangulator.dist_L
    )
    pts_r, _ = cv2.projectPoints(
        P_world, triangulator.R_R, triangulator.t_R, triangulator.K_R, triangulator.dist_R
    )

    uL, vL = float(pts_l[0, 0, 0]), float(pts_l[0, 0, 1])
    uR, vR = float(pts_r[0, 0, 0]), float(pts_r[0, 0, 1])

    # Feed right camera detection to buffer first
    right_det = DetectionResult(
        camera_id="right",
        timestamp=1.0,
        type=ResultType.ARUCO,
        confidence=0.98,
        data={"u": uR, "v": vR, "id": 10},
    )
    triangulator.update_buffers(right_det)

    # Process matching left camera detection at same timestamp
    left_det = DetectionResult(
        camera_id="left",
        timestamp=1.0,
        type=ResultType.ARUCO,
        confidence=0.98,
        data={"u": uL, "v": vL, "id": 10},
    )

    result = triangulator.process_left_result(left_det)

    assert result.source_type == "stereo"
    assert not result.is_occluded
    assert abs(result.world_x - 150.0) < 0.1
    assert abs(result.world_y - 100.0) < 0.1
    assert abs(result.world_z - 50.0) < 0.1


def test_stereo_triangulator_timestamp_skew_fallback(triangulator):
    # If right detection is too old (> delta_t_match), fallback is triggered
    right_det = DetectionResult(
        camera_id="right",
        timestamp=1.0,
        type=ResultType.ARUCO,
        confidence=0.95,
        data={"u": 500.0, "v": 500.0, "id": 10},
    )
    triangulator.update_buffers(right_det)

    # Left detection arrives 0.2s later (delta_t_match is min(0.4*0.033, 0.05) = 0.0132s)
    left_det = DetectionResult(
        camera_id="left",
        timestamp=1.2,
        type=ResultType.ARUCO,
        confidence=0.95,
        data={"u": 500.0, "v": 500.0, "id": 10},
    )

    result = triangulator.process_left_result(left_det)
    # Should trigger fallback rather than stereo
    assert result.source_type != "stereo"
