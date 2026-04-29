import os
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from light_map.map.map_system import MapSystem
from light_map.vision.detectors.aruco_detector import ArucoTokenDetector


def test_token_vertical_projection():
    """
    TDD Test: Verifies that a token's position on the map (Z=0) is derived by
    projecting its 3D position (at Z=h) vertically down, rather than following
    the camera ray to Z=0.
    """
    camera_matrix = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # Camera looking down but tilted 30 degrees around X axis (tilting forward)
    angle = np.radians(150)
    rotation_matrix = np.array(
        [
            [1, 0, 0],
            [0, np.cos(angle), -np.sin(angle)],
            [0, np.sin(angle), np.cos(angle)],
        ],
        dtype=np.float32,
    )

    # Position camera at (0, -500, 866) in world space
    camera_center = np.array([0, -500, 866.0], dtype=np.float32).reshape(3, 1)
    translation_vector = -rotation_matrix @ camera_center
    rotation_vector, _ = cv2.Rodrigues(rotation_matrix)

    # Create Detector
    np.savez(
        "tdd_cam_calib.npz",
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    np.savez(
        "tdd_cam_ext.npz",
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )

    # We patch the ArucoDetector class BEFORE creating our wrapper
    with patch("cv2.aruco.ArucoDetector") as MockDetector:
        mock_instance = MockDetector.return_value

        detector = ArucoTokenDetector(
            calibration_file="tdd_cam_calib.npz", extrinsics_file="tdd_cam_ext.npz"
        )

        # TOKEN at (100, 200, 0) with marker at (100, 200, 50)
        token_top_world = np.array([100.0, 200.0, 50.0], dtype=np.float32)

        # 3. Find where the marker appears in the CAMERA frame
        p_top_cam = rotation_matrix @ token_top_world.reshape(3, 1) + translation_vector
        u = camera_matrix[0, 0] * (p_top_cam[0] / p_top_cam[2]) + camera_matrix[0, 2]
        v = camera_matrix[1, 1] * (p_top_cam[1] / p_top_cam[2]) + camera_matrix[1, 2]

        u_coord = float(u[0])
        v_coord = float(v[0])

        # Integration Check: detect() method
        from light_map.core.common_types import AppConfig

        config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
        map_system = MapSystem(
            config
        )  # Identity mapping mm -> projector pixels -> world

        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Mock corners: (1, 4, 2)
        corners = np.array(
            [
                [
                    [u_coord - 5, v_coord - 5],
                    [u_coord + 5, v_coord - 5],
                    [u_coord + 5, v_coord + 5],
                    [u_coord - 5, v_coord + 5],
                ]
            ],
            dtype=np.float32,
        )
        mock_instance.detectMarkers.return_value = ([corners], np.array([[42]]), [])

        # ppi=25.4 (1mm = 1px)
        tokens = detector.detect(frame, map_system, ppi=25.4, default_height_mm=50.0)

        assert len(tokens) == 1
        token = tokens[0]
        assert token.id == 42
        # Vertical projection to map surface (Z=0)
        assert token.world_x == pytest.approx(100.0, abs=1e-1)
        assert token.world_y == pytest.approx(200.0, abs=1e-1)
        assert token.world_z == 0.0
        # Marker position
        assert token.marker_x == pytest.approx(100.0, abs=1e-1)
        assert token.marker_y == pytest.approx(200.0, abs=1e-1)
        assert token.marker_z == 50.0

    # Cleanup
    if os.path.exists("tdd_cam_calib.npz"):
        os.remove("tdd_cam_calib.npz")
    if os.path.exists("tdd_cam_ext.npz"):
        os.remove("tdd_cam_ext.npz")


if __name__ == "__main__":
    test_token_vertical_projection()
