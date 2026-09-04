"""
Test suite for roi_calculator.
"""

import numpy as np

from light_map.calibration.roi_calculator import compute_roi_pass1, compute_roi_pass2


def test_compute_roi_pass1():
    image_shape = (1080, 1920)
    roi = compute_roi_pass1(image_shape)
    assert roi == (0, 0, 1080, 1920)


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
