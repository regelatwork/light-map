import unittest
from unittest.mock import MagicMock
import numpy as np
import time
import sys
import os

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera_pipeline import CameraPipeline, VisionData


class TestCameraPipeline(unittest.TestCase):
    def setUp(self):
        self.mock_camera = MagicMock()
        self.mock_camera.read.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        self.mock_hands = MagicMock()
        self.mock_hands.process.return_value = MagicMock()

        self.pipeline = CameraPipeline(
            self.mock_camera, self.mock_hands
        )

    def tearDown(self):
        self.pipeline.stop()

    def test_lifecycle(self):
        """Test start and stop."""
        self.pipeline.start()
        self.assertTrue(self.pipeline._thread.is_alive())

        time.sleep(0.1)  # Let it run a bit

        self.pipeline.stop()
        self.assertIsNone(self.pipeline._thread)

    def test_data_flow(self):
        """Test that data flows from camera to get_latest."""
        self.pipeline.start()

        # Wait for data
        timeout = 1.0
        start = time.time()
        data = None
        while time.time() - start < timeout:
            data = self.pipeline.get_latest()
            if data is not None:
                break
            time.sleep(0.01)

        self.assertIsNotNone(data)
        self.assertIsInstance(data, VisionData)
        self.assertEqual(data.frame.shape, (100, 100, 3))
        self.assertTrue(self.mock_camera.read.called)
        self.assertTrue(self.mock_hands.process.called)

    def test_frame_id_increment(self):
        """Test that frame IDs increment."""
        self.pipeline.start()

        time.sleep(0.2)
        data1 = self.pipeline.get_latest()

        time.sleep(0.2)
        data2 = self.pipeline.get_latest()

        self.assertIsNotNone(data1)
        self.assertIsNotNone(data2)
        self.assertGreater(data2.frame_id, data1.frame_id)


if __name__ == "__main__":
    unittest.main()
