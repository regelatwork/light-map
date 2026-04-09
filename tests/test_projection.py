import numpy as np
import cv2
import pytest
from light_map.rendering.projection import CameraProjectionModel


def test_camera_projection_model_parallax_math():
    # Setup mock calibration
    # Camera at (0, 0, 1000mm) looking straight down
    camera_matrix = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # rotation_matrix = [1 0 0; 0 -1 0; 0 0 -1] (Camera Z forward is World -Z down)
    rotation_matrix = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rotation_vector, _ = cv2.Rodrigues(rotation_matrix)
    translation_vector = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    model = CameraProjectionModel(
        camera_matrix, distortion_coefficients, rotation_vector, translation_vector
    )

    # 1. Test point at center (960, 540)
    # Ray goes through (0, 0, 1) in normalized camera space.
    # World direction: R^T * [0, 0, 1] = [0, 0, -1]
    # Intersection with Z=0: [0, 0, 1000] + 1000 * [0, 0, -1] = [0, 0, 0]
    pixel_points = np.array([[960, 540]], dtype=np.float32)
    world_points = model.reconstruct_world_points(pixel_points, height_mm=0.0)

    assert world_points.shape == (1, 2)
    assert world_points[0, 0] == pytest.approx(0.0, abs=1e-4)
    assert world_points[0, 1] == pytest.approx(0.0, abs=1e-4)

    # Intersection with Z=100: [0, 0, 1000] + 900 * [0, 0, -1] = [0, 0, 100]
    world_points_100 = model.reconstruct_world_points(pixel_points, height_mm=100.0)
    assert world_points_100[0, 0] == pytest.approx(0.0, abs=1e-4)
    assert world_points_100[0, 1] == pytest.approx(0.0, abs=1e-4)

    # 2. Test point offset (1060, 540)
    # dx_cam = 100 / 1000 = 0.1
    # normalized ray = [0.1, 0, 1]
    # world ray = R^T * [0.1, 0, 1] = [0.1, 0, -1]
    # Intersection with Z=0 (s=1000): [100, 0, 0]
    pixel_points_offset = np.array([[1060, 540]], dtype=np.float32)
    world_points_offset = model.reconstruct_world_points(
        pixel_points_offset, height_mm=0.0
    )
    assert world_points_offset[0, 0] == pytest.approx(100.0, abs=1e-4)
    assert world_points_offset[0, 1] == pytest.approx(0.0, abs=1e-4)

    # Intersection with Z=100 (s=900): [90, 0, 100]
    world_points_offset_100 = model.reconstruct_world_points(
        pixel_points_offset, height_mm=100.0
    )
    assert world_points_offset_100[0, 0] == pytest.approx(90.0, abs=1e-4)
    assert world_points_offset_100[0, 1] == pytest.approx(0.0, abs=1e-4)


def test_camera_projection_model_vectorization():
    camera_matrix = np.eye(3, dtype=np.float32)
    distortion_coefficients = np.zeros(5, dtype=np.float32)
    rotation_vector = np.zeros((3, 1), dtype=np.float32)
    translation_vector = np.array([[0], [0], [10]], dtype=np.float32)

    model = CameraProjectionModel(
        camera_matrix, distortion_coefficients, rotation_vector, translation_vector
    )

    # Multiple points
    pixel_points = np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32)
    world_points = model.reconstruct_world_points(pixel_points, height_mm=0.0)

    assert world_points.shape == (3, 2)


def test_camera_projection_model_project_world_to_camera():
    camera_matrix = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)
    rotation_matrix = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rotation_vector, _ = cv2.Rodrigues(rotation_matrix)
    translation_vector = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    model = CameraProjectionModel(
        camera_matrix, distortion_coefficients, rotation_vector, translation_vector
    )

    # World point at origin [0, 0, 0] should project to center [960, 540]
    world_points = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    pixel_points = model.project_world_to_camera(world_points)

    assert pixel_points[0, 0] == pytest.approx(960.0, abs=1e-4)
    assert pixel_points[0, 1] == pytest.approx(540.0, abs=1e-4)
