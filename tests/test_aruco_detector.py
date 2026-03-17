import cv2
import numpy as np
import os
import pytest
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem


def test_aruco_parallax_correction_math():
    # Setup mock calibration
    camera_matrix = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # Camera at (0, 0, 1000mm) looking straight down
    # World Z is up, Camera Z is forward.
    # rotation_matrix = [1 0 0; 0 -1 0; 0 0 -1]
    rotation_matrix = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rotation_vector, _ = cv2.Rodrigues(rotation_matrix)
    translation_vector = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    # Save to temp files
    np.savez(
        "test_cam_calib.npz",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    np.savez(
        "test_cam_ext.npz",
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )

    detector = ArucoTokenDetector(
        calibration_file="test_cam_calib.npz", extrinsics_file="test_cam_ext.npz"
    )

    # 1. Test point at center (960, 540)
    # Ray goes through (0, 0) in camera space.
    # Plane Z=0 (table) should give (0, 0) in world space.
    # Plane Z=100 (token top) should still give (0, 0) because it's directly under camera.
    pixel_points_center = np.array([[960, 540]], dtype=np.float32)
    world_points_res0 = detector.projection_model.reconstruct_world_points(
        pixel_points_center, 0
    )
    world_x0, world_y0 = world_points_res0[0]
    assert world_x0 == pytest.approx(0.0, abs=1e-4)
    assert world_y0 == pytest.approx(0.0, abs=1e-4)

    world_points_res100 = detector.projection_model.reconstruct_world_points(
        pixel_points_center, 100
    )
    world_x100, world_y100 = world_points_res100[0]
    assert world_x100 == pytest.approx(0.0, abs=1e-4)
    assert world_y100 == pytest.approx(0.0, abs=1e-4)

    # 2. Test point offset
    # Let's say point is at (1060, 540) in pixels.
    pixel_points_offset = np.array([[1060, 540]], dtype=np.float32)
    world_points_res_off = detector.projection_model.reconstruct_world_points(
        pixel_points_offset, 0
    )
    world_x_off, world_y_off = world_points_res_off[0]
    assert world_x_off == pytest.approx(100.0, abs=1e-4)
    assert world_y_off == pytest.approx(0.0, abs=1e-4)

    # At Z=100 (token top): 1000 + s*(-1) = 100 => s = 900.
    world_points_res_h = detector.projection_model.reconstruct_world_points(
        pixel_points_offset, 100
    )
    world_x_h, world_y_h = world_points_res_h[0]
    assert world_x_h == pytest.approx(90.0, abs=1e-4)
    assert world_y_h == pytest.approx(0.0, abs=1e-4)

    # Cleanup
    os.remove("test_cam_calib.npz")
    os.remove("test_cam_ext.npz")


def test_aruco_detect_integration():
    # Setup mock calibration
    camera_matrix = np.array(
        [[1000.0, 0.0, 320.0], [0.0, 1000.0, 240.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)
    rotation_matrix = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rotation_vector, _ = cv2.Rodrigues(rotation_matrix)
    translation_vector = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    np.savez(
        "test_cam_calib.npz",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    np.savez(
        "test_cam_ext.npz",
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )

    detector = ArucoTokenDetector(
        calibration_file="test_cam_calib.npz", extrinsics_file="test_cam_ext.npz"
    )

    # Create synthetic frame with ArUco marker
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, 42, 100)
    marker_img = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    # ArUco needs a quiet zone (white border)
    # Let's put a white square behind it
    frame[180:300, 360:480] = 255

    # Place marker such that its center is at (420, 240) in pixels
    # marker size is 100x100
    frame[190:290, 370:470] = marker_img

    # MapSystem (Identity for simplicity)
    map_system = MapSystem(1920, 1080)

    # Detect
    tokens = detector.detect(frame, map_system, ppi=25.4, default_height_mm=0.0)

    assert len(tokens) == 1
    assert tokens[0].id == 42

    assert tokens[0].world_x == pytest.approx(99.5, abs=1e-1)
    assert tokens[0].world_y == pytest.approx(0.5, abs=1e-1)

    # Cleanup
    os.remove("test_cam_calib.npz")
    os.remove("test_cam_ext.npz")
