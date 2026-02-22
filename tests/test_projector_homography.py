import numpy as np
import pytest
import cv2
from light_map.projector import compute_projector_homography


def test_compute_projector_homography_success(monkeypatch):
    # Setup pattern params
    params = {"rows": 3, "cols": 3, "square_size": 100, "start_x": 100, "start_y": 100}

    # Inner corners: (2, 2)
    # Target intersections in projector space:
    # (100+100, 100+100) = (200, 200)
    # (100+200, 100+100) = (300, 200)
    # (100+100, 100+200) = (200, 300)
    # (100+200, 100+200) = (300, 300)

    # Mock camera image (must be at least gray)
    img = np.zeros((600, 800, 3), dtype=np.uint8)

    # Mock findChessboardCorners
    # Corners are [u, v]
    mock_corners = np.array(
        [[[20, 20]], [[30, 20]], [[20, 30]], [[30, 30]]], dtype=np.float32
    )

    def mock_find_corners(gray, size, corners):
        assert size == (2, 2)
        return True, mock_corners

    monkeypatch.setattr(cv2, "findChessboardCorners", mock_find_corners)

    # Mock findHomography
    mock_H = np.eye(3) * 10

    def mock_find_homography(src, dst):
        # Verify mapping logic
        expected_dst = np.array(
            [[200, 200], [300, 200], [200, 300], [300, 300]], dtype=np.float32
        )
        assert np.allclose(dst, expected_dst)
        return mock_H, None

    monkeypatch.setattr(cv2, "findHomography", mock_find_homography)

    H, cam_pts, proj_pts = compute_projector_homography(img, params)

    assert np.allclose(H, mock_H)
    assert cam_pts.shape == (4, 2)
    assert proj_pts.shape == (4, 2)


def test_compute_projector_homography_fail(monkeypatch):
    params = {"rows": 3, "cols": 3, "square_size": 100, "start_x": 100, "start_y": 100}
    img = np.zeros((600, 800, 3), dtype=np.uint8)

    def mock_find_corners(gray, size, corners):
        return False, None

    monkeypatch.setattr(cv2, "findChessboardCorners", mock_find_corners)

    with pytest.raises(RuntimeError, match="Chessboard pattern not detected"):
        compute_projector_homography(img, params)
