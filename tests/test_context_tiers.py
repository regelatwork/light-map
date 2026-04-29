import pickle
import unittest
from unittest.mock import MagicMock

import numpy as np

from light_map.core.app_context import (
    AppContext,
    MainContext,
    RemoteContext,
    VisionContext,
)
from light_map.core.common_types import AppConfig
from light_map.rendering.projection import CameraProjectionModel
from light_map.state.world_state import WorldState


class TestContextTiers(unittest.TestCase):
    def setUp(self):
        # Create a dummy AppConfig
        self.config = AppConfig(
            width=1920,
            height=1080,
            projector_matrix=np.eye(3),
        )

        # Create a dummy CameraProjectionModel
        self.projection_model = CameraProjectionModel(
            camera_matrix=np.eye(3),
            distortion_coefficients=np.zeros(5),
            rotation_vector=np.zeros(3),
            translation_vector=np.zeros(3),
        )

        # Create a dummy WorldState
        self.state = WorldState()

    def test_vision_context_attributes_and_pickle(self):
        ctx = VisionContext(
            app_config=self.config, camera_projection_model=self.projection_model
        )
        self.assertEqual(ctx.app_config.width, 1920)
        self.assertIs(ctx.camera_projection_model, self.projection_model)

        # Verify picklable
        data = pickle.dumps(ctx)
        ctx2 = pickle.loads(data)
        self.assertEqual(ctx2.app_config.width, 1920)
        np.testing.assert_array_equal(
            ctx2.app_config.projector_matrix, self.config.projector_matrix
        )
        self.assertIsNotNone(ctx2.camera_projection_model)

    def test_remote_context_attributes_and_pickle(self):
        ctx = RemoteContext(app_config=self.config, state=self.state)
        self.assertEqual(ctx.app_config.width, 1920)
        self.assertIs(ctx.state, self.state)

        # Verify picklable
        data = pickle.dumps(ctx)
        ctx2 = pickle.loads(data)
        self.assertEqual(ctx2.app_config.width, 1920)
        self.assertIsNotNone(ctx2.state)
        # Check an atom value
        self.assertEqual(ctx2.state.tokens, [])

    def test_main_context_attributes(self):
        # MainContext should have everything AppContext has
        mock_renderer = MagicMock()
        mock_map_system = MagicMock()
        mock_map_config = MagicMock()
        mock_notifications = MagicMock()
        mock_analytics = MagicMock()
        mock_events = MagicMock()

        ctx = MainContext(
            app_config=self.config,
            renderer=mock_renderer,
            map_system=mock_map_system,
            map_config_manager=mock_map_config,
            notifications=mock_notifications,
            analytics=mock_analytics,
            events=mock_events,
            state=self.state,
        )

        self.assertEqual(ctx.app_config.width, 1920)
        self.assertIs(ctx.renderer, mock_renderer)
        self.assertIs(ctx.map_system, mock_map_system)
        self.assertIs(ctx.state, self.state)

        # Verify MainContext is an instance of AppContext
        self.assertTrue(isinstance(ctx, AppContext))


if __name__ == "__main__":
    unittest.main()
