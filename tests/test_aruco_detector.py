import cv2
import numpy as np
import os
import pytest
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem


def test_aruco_parallax_correction_math():
    # Setup mock calibration
    K = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist = np.zeros(5, dtype=np.float32)

    # Camera at (0, 0, 1000mm) looking straight down
    # World Z is up, Camera Z is forward.
    # R = [1 0 0; 0 -1 0; 0 0 -1]
    R = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rvec, _ = cv2.Rodrigues(R)
    tvec = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    # Save to temp files
    np.savez("test_cam_calib.npz", camera_matrix=K, dist_coeffs=dist)
    np.savez("test_cam_ext.npz", rvec=rvec, tvec=tvec)

    detector = ArucoTokenDetector(
        calibration_file="test_cam_calib.npz", extrinsics_file="test_cam_ext.npz"
    )

    # 1. Test point at center (960, 540)
    # Ray goes through (0, 0) in camera space.
    # Plane Z=0 (table) should give (0, 0) in world space.
    # Plane Z=100 (token top) should still give (0, 0) because it's directly under camera.
    wx0, wy0 = detector._parallax_correction(960, 540, 0)
    assert wx0 == pytest.approx(0.0, abs=1e-4)
    assert wy0 == pytest.approx(0.0, abs=1e-4)

    wx100, wy100 = detector._parallax_correction(960, 540, 100)
    assert wx100 == pytest.approx(0.0, abs=1e-4)
    assert wy100 == pytest.approx(0.0, abs=1e-4)

    # 2. Test point offset
    # Let's say point is at (1060, 540) in pixels.
    # x_cam = (1060 - 960) / 1000 = 0.1
    # y_cam = 0
    # Ray direction in camera: [0.1, 0, 1]
    # Ray direction in world: R^T * [0.1, 0, 1] = [1 0 0; 0 -1 0; 0 0 -1] * [0.1, 0, 1] = [0.1, 0, -1]
    # Camera center in world: C = [0, 0, 1000]
    # P = C + s * [0.1, 0, -1]
    # At Z=0: 1000 + s*(-1) = 0 => s = 1000.
    # P = [0, 0, 1000] + 1000 * [0.1, 0, -1] = [100, 0, 0]
    wx_off, wy_off = detector._parallax_correction(1060, 540, 0)
    assert wx_off == pytest.approx(100.0, abs=1e-4)
    assert wy_off == pytest.approx(0.0, abs=1e-4)

    # At Z=100 (token top): 1000 + s*(-1) = 100 => s = 900.
    # P = [0, 0, 1000] + 900 * [0.1, 0, -1] = [90, 0, 100]
    wx_h, wy_h = detector._parallax_correction(1060, 540, 100)
    assert wx_h == pytest.approx(90.0, abs=1e-4)
    assert wy_h == pytest.approx(0.0, abs=1e-4)

    # Cleanup
    os.remove("test_cam_calib.npz")
    os.remove("test_cam_ext.npz")


def test_aruco_detect_integration():
    # Setup mock calibration
    K = np.array(
        [[1000.0, 0.0, 320.0], [0.0, 1000.0, 240.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist = np.zeros(5, dtype=np.float32)
    R = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    rvec, _ = cv2.Rodrigues(R)
    tvec = np.array([[0.0], [0.0], [1000.0]], dtype=np.float32)

    np.savez("test_cam_calib.npz", camera_matrix=K, dist_coeffs=dist)
    np.savez("test_cam_ext.npz", rvec=rvec, tvec=tvec)

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

    # PPI = 100 / 25.4 (so 1mm = 1 projector pixel)
    # If 1mm = 1px, then 1 inch = 25.4px. PPI = 25.4.

    # Detect
    tokens = detector.detect(frame, map_system, ppi=25.4, default_height_mm=0.0)

    assert len(tokens) == 1
    assert tokens[0].id == 42

    # dx = 419.5 - 320 = 99.5 pixels.
    # dy = 239.5 - 240 = -0.5 pixels.
    # Since K_fx = 1000, t_z = 1000, h=0:
    # wx = (99.5 / 1000) * 1000 = 99.5mm.
    # wy = (0.5 / 1000) * 1000 = 0.5mm. (Y flip by R)
    # wx_svg should be 99.5 (identity map_system)

    assert tokens[0].world_x == pytest.approx(99.5, abs=1e-1)
    assert tokens[0].world_y == pytest.approx(0.5, abs=1e-1)

    # Cleanup
    os.remove("test_cam_calib.npz")
    os.remove("test_cam_ext.npz")
