import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import time
import sys
import os

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera_pipeline import CameraPipeline, VisionData
from light_map.common_types import Token, AppConfig


class TestVisionParallelization(unittest.TestCase):
    def setUp(self):
        self.mock_camera = MagicMock()
        # Return a frame each time read is called
        self.mock_camera.read.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        self.mock_hands = MagicMock()
        self.mock_hands.process.return_value = MagicMock()

        self.mock_tracking_coordinator = MagicMock()
        # Mock TrackingCoordinator to update map_system.ghost_tokens
        def mock_process(frame, config, map_system, map_config, **kwargs):
            map_system.ghost_tokens = [Token(id=1, world_x=10.0, world_y=20.0)]
        self.mock_tracking_coordinator.process_aruco_tracking.side_effect = mock_process

        self.mock_app_config = MagicMock(spec=AppConfig)
        self.mock_map_system = MagicMock()
        self.mock_map_system.ghost_tokens = []
        self.mock_map_config = MagicMock()

        self.pipeline = CameraPipeline(
            self.mock_camera,
            self.mock_hands,
            tracking_coordinator=self.mock_tracking_coordinator,
            app_config=self.mock_app_config,
            map_system=self.mock_map_system,
            map_config=self.mock_map_config,
        )

    def tearDown(self):
        self.pipeline.stop()

    def test_aruco_runs_in_pipeline(self):
        """Test that ArUco tracking is executed within the CameraPipeline thread."""
        self.pipeline.start()

        # Wait for data
        timeout = 2.0
        start = time.time()
        data = None
        while time.time() - start < timeout:
            data = self.pipeline.get_latest()
            if data is not None and data.tokens:
                break
            time.sleep(0.05)

        self.assertIsNotNone(data, "Did not receive VisionData from pipeline.")
        self.assertTrue(len(data.tokens) > 0, "No tokens found in VisionData.")
        self.assertEqual(data.tokens[0].id, 1)
        self.assertTrue(self.mock_tracking_coordinator.process_aruco_tracking.called)

    def test_vision_data_tokens_snapshot(self):
        """Test that VisionData captures a snapshot of tokens."""
        self.pipeline.start()

        # Wait for first data
        timeout = 2.0
        start = time.time()
        data1 = None
        while time.time() - start < timeout:
            data1 = self.pipeline.get_latest()
            if data1 is not None and data1.tokens:
                break
            time.sleep(0.05)

        self.assertIsNotNone(data1)
        self.assertEqual(len(data1.tokens), 1)

        # Change tokens in coordinator for next frame
        def mock_process_v2(frame, config, map_system, map_config, **kwargs):
            map_system.ghost_tokens = [Token(id=2, world_x=30.0, world_y=40.0)]
        self.mock_tracking_coordinator.process_aruco_tracking.side_effect = mock_process_v2

        # Wait for next data
        start = time.time()
        data2 = None
        while time.time() - start < timeout:
            data2 = self.pipeline.get_latest()
            if data2 is not None and data2.frame_id > data1.frame_id:
                break
            time.sleep(0.05)

        self.assertIsNotNone(data2)
        self.assertEqual(data2.tokens[0].id, 2)
        # Ensure data1 tokens are unchanged (snapshot)
        self.assertEqual(data1.tokens[0].id, 1)


if __name__ == "__main__":
    unittest.main()
