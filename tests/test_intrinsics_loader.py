"""
Test suite for intrinsics_loader.
"""


import numpy as np
import pytest

from light_map.calibration.intrinsics_loader import load_intrinsics


@pytest.fixture
def mock_calib_dir(tmp_path):
    # Create a directory with mock .npz files
    # We can't easily mock np.load in a simple way without complex mocking,
    # so we'll just write real (dummy) .npz files.

    def create_npz(name, K, dist):
        data = {"K": K, "dist": dist}
        np.savez_compressed(tmp_path / name, **data)

    create_npz("camera_calibration.npz", np.eye(3), np.zeros(5))
    return tmp_path


def test_load_intrinsics_left_fallback(mock_calib_dir):
    # Only camera_calibration.npz exists
    K, dist = load_intrinsics("left", mock_calib_dir)
    assert np.array_equal(K, np.eye(3))
    assert np.array_equal(dist, np.zeros(5))


def test_load_intrinsics_right_fallback(mock_calib_dir):
    # Only camera_calibration.npz exists
    K, dist = load_intrinsics("right", mock_calib_dir)
    assert np.array_equal(K, np.eye(3))
    assert np.array_equal(dist, np.zeros(5))


def test_load_intrinsics_left_success(mock_calib_dir):
    # Create camera_left_calibration.npz
    K = np.eye(3) * 2
    dist = np.array([0, 0, 0, 0, 0])
    # We need to save it correctly as a .npz with a dictionary
    data = {"K": K, "dist": dist}
    np.savez_compressed(mock_calib_dir / "camera_left_calibration.npz", **data)

    K, dist = load_intrinsics("left", mock_calib_dir)
    assert np.array_equal(K, np.eye(3) * 2)


def test_load_intrinsics_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_intrinsics("left", tmp_path)
