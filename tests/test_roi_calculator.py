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


def test_compute_roi_pass2_placeholder():
    # Since it's a placeholder, it might not do anything yet.
    # I'll update it with logic first.
    image_shape = (1080, 1920)
    r_left = np.eye(3)
    t_left = np.zeros(3)
    r_right = np.eye(3)
    t_right = np.zeros(3)

    roi_left, roi_right = compute_roi_pass2(image_shape, r_left, t_left, r_right, t_right)
    assert isinstance(roi_left, tuple)
    assert isinstance(roi_right, tuple)
