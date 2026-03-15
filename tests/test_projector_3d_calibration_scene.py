import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from light_map.core.app_context import AppContext
from light_map.common_types import SceneId, GestureType, Action
from light_map.scenes.calibration_scenes import Projector3DCalibrationScene, Projector3DCalibStage


class TestProjector3DCalibrationScene(unittest.TestCase):
    def setUp(self):
        self.mock_context = MagicMock(spec=AppContext)
        self.mock_context.app_config = MagicMock()
        self.mock_context.app_config.width = 1280
        self.mock_context.app_config.height = 720
        self.mock_context.app_config.calibration_box_height_mm = 78.0
        self.mock_context.app_config.storage_manager = MagicMock()
        self.mock_context.notifications = MagicMock()

    def test_initialization(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        self.assertEqual(scene.stage, Projector3DCalibStage.START)
        self.assertEqual(len(scene.correspondences), 0)
        self.assertIsNotNone(scene.layer)

    def test_stage_transition_start_to_place(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()
        
        # First update should transition to PLACE_BOX
        transition = scene.update([], [], 1.0)
        self.assertIsNone(transition)
        self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)

    def test_victory_gesture_triggers_capture(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()
        scene.update([], [], 1.0) # Move to PLACE_BOX
        
        # Mock hand input with Victory gesture
        mock_input = MagicMock()
        mock_input.gesture = GestureType.VICTORY
        
        # Update with victory gesture
        with patch.object(scene, '_do_capture') as mock_capture:
            scene.update([mock_input], [], 5.0)
            self.assertEqual(scene.stage, Projector3DCalibStage.CAPTURING)
            
            # Next update should move back to PLACE_BOX (since index < max)
            scene.update([], [], 6.0)
            self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)
            mock_capture.assert_called_once()

    def test_layer_rendering_no_crash(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()
        # This will call _update_layer_markers which sets instructions
        
        # Manually trigger a render update
        patches = scene.layer._generate_patches(1.0)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].data.shape[2], 4) # Should be BGRA

    def test_get_active_layers(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        mock_app = MagicMock()
        mock_app.notification_layer = MagicMock()
        mock_app.cursor_layer = MagicMock()
        
        layers = scene.get_active_layers(mock_app)
        self.assertIn(scene.layer, layers)
        self.assertIn(mock_app.notification_layer, layers)
        self.assertIn(mock_app.cursor_layer, layers)
        # Menu layer should NOT be here
        self.assertNotIn(getattr(mock_app, 'menu_layer', None), layers)


if __name__ == "__main__":
    unittest.main()
