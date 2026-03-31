import unittest
import numpy as np
from unittest.mock import MagicMock
import sys
import os

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem
from light_map.vision.projection import CameraProjectionModel


class TestArucoResizing(unittest.TestCase):
    def test_aruco_detection_at_high_res(self):
        # Create a 4K image with an ArUco marker
        width, height = 3840, 2160
        frame = np.ones((height, width, 3), dtype=np.uint8) * 200

        detector = ArucoTokenDetector()
        detector.target_width = 1280  # Force resizing

        # Mock the detector's detectMarkers
        mock_detector = MagicMock()
        detector.detector = mock_detector

        # Simulated detection in 1280px wide frame (scale = 1280 / 3840 = 1/3)
        # Marker center at (1920, 1080) in 4K -> (640, 360) in 1280px
        scale = 1280 / 3840
        cx_small, cy_small = 1920 * scale, 1080 * scale
        mock_corners = [
            np.array(
                [
                    [
                        [cx_small - 10, cy_small - 10],
                        [cx_small + 10, cy_small - 10],
                        [cx_small + 10, cy_small + 10],
                        [cx_small - 10, cy_small + 10],
                    ]
                ],
                dtype=np.float32,
            )
        ]
        mock_ids = np.array([[1]], dtype=np.int32)
        mock_detector.detectMarkers.return_value = (mock_corners, mock_ids, [])

        # Mock calibration and map_system
        detector.camera_matrix = np.eye(3)
        detector.rotation_vector = np.zeros((3, 1))
        detector.translation_vector = np.zeros((3, 1))
        detector.projection_model = MagicMock(spec=CameraProjectionModel)
        detector.projection_model.reconstruct_world_points_3d.return_value = np.array(
            [[100.0, 200.0, 0.0]]
        )

        mock_map_system = MagicMock(spec=MapSystem)
        mock_map_system.width = 1920
        mock_map_system.height = 1080
        mock_map_system.screen_to_world.return_value = (100.0, 200.0)
        mock_map_system.world_mm_to_svg.return_value = (100.0, 200.0)

        tokens = detector.detect(frame, mock_map_system)

        self.assertEqual(len(tokens), 1)
        self.assertEqual(tokens[0].id, 1)

        # Check if parallax correction was called with SCALED coordinates
        # Actually ArucoTokenDetector scales corners BACK to original resolution
        # u, v should be (1920, 1080)
        # In our mock, corners are at 640, 360 in small image -> 1920, 1080 in large image.

        # Since we scaled back, reconstruct_world_points should receive (1920, 1080)
        tokens = detector.detect(frame, mock_map_system)
        call_args = detector.projection_model.reconstruct_world_points_3d.call_args[0]
        pixel_points_call = call_args[0]
        u_call, v_call = pixel_points_call[0]

        self.assertAlmostEqual(u_call, 1920.0, places=1)
        self.assertAlmostEqual(v_call, 1080.0, places=1)


if __name__ == "__main__":
    unittest.main()
