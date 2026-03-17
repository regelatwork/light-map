import numpy as np
import cv2
import pytest
from light_map.vision.projection import CameraProjectionModel


def test_camera_projection_model_parallax_math():
    # Setup mock calibration
    # Camera at (0, 0, 1000mm) looking straight down
    K = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist = np.zeros(5, dtype=np.float32)

    # R = [1 0 0; 0 -1 0; 0 0 -1] (Camera Z forward is World -Z down)
    R = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rvec, _ = cv2.Rodrigues(R)
    tvec = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    model = CameraProjectionModel(K, dist, rvec, tvec)

    # 1. Test point at center (960, 540)
    # Ray goes through (0, 0, 1) in normalized camera space.
    # World direction: R^T * [0, 0, 1] = [0, 0, -1]
    # Intersection with Z=0: [0, 0, 1000] + 1000 * [0, 0, -1] = [0, 0, 0]
    pts = np.array([[960, 540]], dtype=np.float32)
    world_pts = model.reconstruct_world_points(pts, height_mm=0.0)

    assert world_pts.shape == (1, 2)
    assert world_pts[0, 0] == pytest.approx(0.0, abs=1e-4)
    assert world_pts[0, 1] == pytest.approx(0.0, abs=1e-4)

    # Intersection with Z=100: [0, 0, 1000] + 900 * [0, 0, -1] = [0, 0, 100]
    world_pts_100 = model.reconstruct_world_points(pts, height_mm=100.0)
    assert world_pts_100[0, 0] == pytest.approx(0.0, abs=1e-4)
    assert world_pts_100[0, 1] == pytest.approx(0.0, abs=1e-4)

    # 2. Test point offset (1060, 540)
    # dx_cam = 100 / 1000 = 0.1
    # normalized ray = [0.1, 0, 1]
    # world ray = R^T * [0.1, 0, 1] = [0.1, 0, -1]
    # Intersection with Z=0 (s=1000): [100, 0, 0]
    pts_off = np.array([[1060, 540]], dtype=np.float32)
    world_pts_off = model.reconstruct_world_points(pts_off, height_mm=0.0)
    assert world_pts_off[0, 0] == pytest.approx(100.0, abs=1e-4)
    assert world_pts_off[0, 1] == pytest.approx(0.0, abs=1e-4)

    # Intersection with Z=100 (s=900): [90, 0, 100]
    world_pts_off_100 = model.reconstruct_world_points(pts_off, height_mm=100.0)
    assert world_pts_off_100[0, 0] == pytest.approx(90.0, abs=1e-4)
    assert world_pts_off_100[0, 1] == pytest.approx(0.0, abs=1e-4)


def test_camera_projection_model_vectorization():
    K = np.eye(3, dtype=np.float32)
    dist = np.zeros(5, dtype=np.float32)
    rvec = np.zeros((3, 1), dtype=np.float32)
    tvec = np.array([[0], [0], [10]], dtype=np.float32)

    model = CameraProjectionModel(K, dist, rvec, tvec)

    # Multiple points
    pts = np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32)
    world_pts = model.reconstruct_world_points(pts, height_mm=0.0)

    assert world_pts.shape == (3, 2)


def test_camera_projection_model_project_world_to_camera():
    K = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist = np.zeros(5, dtype=np.float32)
    R = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rvec, _ = cv2.Rodrigues(R)
    tvec = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    model = CameraProjectionModel(K, dist, rvec, tvec)

    # World point at origin [0, 0, 0] should project to center [960, 540]
    world_pts = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    pixel_pts = model.project_world_to_camera(world_pts)

    assert pixel_pts[0, 0] == pytest.approx(960.0, abs=1e-4)
    assert pixel_pts[0, 1] == pytest.approx(540.0, abs=1e-4)
