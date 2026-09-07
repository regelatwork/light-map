"""
Test suite for roi_calculator.
"""

import numpy as np

from light_map.calibration.roi_calculator import compute_roi_pass1, compute_roi_pass2


def test_compute_roi_pass1():
    image_shape = (1080, 1920)
    # Markers are expected to be a list of (id, corners)
    markers = [
        (42, np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)),
        (43, np.array([[100, 0], [200, 0], [200, 100], [100, 100]], dtype=np.float32)),
        (44, np.array([[200, 0], [300, 0], [300, 100], [200, 100]], dtype=np.float32)),
        (45, np.array([[300, 0], [400, 0], [400, 100], [300, 100]], dtype=np.float32)),
        (46, np.array([[0, 100], [100, 100], [100, 200], [0, 200]], dtype=np.float32)),
        (47, np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)),
        (48, np.array([[200, 100], [300, 100], [300, 200], [200, 200]], dtype=np.float32)),
        (49, np.array([[300, 100], [400, 100], [400, 200], [300, 200]], dtype=np.float32)),
    ]
    roi = compute_roi_pass1(image_shape, markers)
    assert roi == (0, 0, 440, 220)


def test_compute_roi_pass2_downward_camera():
    image_shape = (1080, 1920)
    # Downward-looking camera: R = diag(1, -1, -1)
    r_down = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]], dtype=np.float32)
    t_cam = np.array([0.0, 0.0, 1000.0], dtype=np.float32)
    K = np.array([[800.0, 0, 960.0], [0, 800.0, 540.0], [0, 0, 1.0]], dtype=np.float32)

    corners_3d = np.array(
        [[-300.0, -200.0, 0.0], [300.0, -200.0, 0.0], [300.0, 200.0, 0.0], [-300.0, 200.0, 0.0]],
        dtype=np.float32,
    )

    # 1. Flat tabletop (Z = 0)
    roi_l_flat, roi_r_flat = compute_roi_pass2(
        image_shape,
        r_down,
        t_cam,
        r_down,
        t_cam,
        max_height_mm=0.0,
        corners_3d=corners_3d,
        k_left=K,
        k_right=K,
    )

    # 2. Elevated tabletop with 200mm vertical parallax volume
    roi_l_200, roi_r_200 = compute_roi_pass2(
        image_shape,
        r_down,
        t_cam,
        r_down,
        t_cam,
        max_height_mm=200.0,
        corners_3d=corners_3d,
        k_left=K,
        k_right=K,
    )

    # Validate coordinate positivity and bounds
    for roi in [roi_l_flat, roi_r_flat, roi_l_200, roi_r_200]:
        x, y, w, h = roi
        assert x >= 0
        assert y >= 0
        assert x + w <= 1920
        assert y + h <= 1080
        assert w > 0
        assert h > 0

    # Elevated envelope (Z=200mm closer to camera) must be strictly larger than flat envelope
    assert roi_l_200[2] > roi_l_flat[2]  # width is larger
    assert roi_l_200[3] > roi_l_flat[3]  # height is larger


def test_compute_roi_pass2_points_behind_camera():
    image_shape = (1080, 1920)
    # Camera looking away: t = [0, 0, -1000], points at Z >= 0 are behind camera
    r_identity = np.eye(3, dtype=np.float32)
    t_behind = np.array([0.0, 0.0, -1000.0], dtype=np.float32)

    roi_l, roi_r = compute_roi_pass2(
        image_shape,
        r_identity,
        t_behind,
        r_identity,
        t_behind,
        max_height_mm=200.0,
    )

    # Should safely fallback to full image bounds rather than crashing
    assert roi_l == (0, 0, 1920, 1080)
    assert roi_r == (0, 0, 1920, 1080)
