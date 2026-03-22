import unittest
from unittest.mock import MagicMock, patch
from light_map.core.app_context import AppContext
from light_map.common_types import GestureType
from light_map.scenes.calibration_scenes import (
    Projector3DCalibrationScene,
    Projector3DCalibStage,
)


class TestProjector3DCalibrationScene(unittest.TestCase):
    def setUp(self):
        self.mock_context = MagicMock(spec=AppContext)
        self.mock_context.app_config = MagicMock()
        self.mock_context.app_config.width = 1280
        self.mock_context.app_config.height = 720
        self.mock_context.app_config.calibration_box_height_mm = 78.0
        self.mock_context.app_config.storage_manager = MagicMock()
        self.mock_context.notifications = MagicMock()
        self.mock_context.events = MagicMock()
        self.mock_context.analytics = MagicMock()
        self.mock_context.raw_aruco = {"ids": [], "corners": []}
        self.mock_context.state = MagicMock()
        self.mock_context.state.scene_version = 1

    def test_initialization(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        self.assertEqual(scene.stage, Projector3DCalibStage.START)
        self.assertEqual(len(scene.correspondences), 0)
        self.assertIsNotNone(scene.pattern_layer)
        self.assertIsNotNone(scene.feedback_layer)

    def test_stage_transition_start_to_place(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()

        # First update should transition to PLACE_BOX
        transition = scene.update([], [], 1.0)
        self.assertIsNone(transition)
        self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)

    def test_alternating_gestures_trigger_capture(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()
        scene.update([], [], 1.0)  # Move to PLACE_BOX (Step 1)
        # In current implementation, if START, it moves to PLACE_BOX immediately but we might need
        # to ensure it's actually in PLACE_BOX for the next call to process gestures.
        self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)
        self.assertEqual(scene.current_box_pos_idx, 0)

        # 1. Step 1 expects VICTORY
        mock_victory = MagicMock()
        mock_victory.gesture = GestureType.VICTORY

        with patch.object(
            scene,
            "_do_capture",
            side_effect=lambda: setattr(scene, "current_box_pos_idx", 1),
        ):
            scene.update([mock_victory], [], 5.0)
            self.assertEqual(scene.stage, Projector3DCalibStage.CAPTURING)
            scene.update([], [], 6.0)  # Finish capture
            self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)
            self.assertEqual(scene.current_box_pos_idx, 1)

        # 2. Step 2 expects SHAKA
        mock_shaka = MagicMock()
        mock_shaka.gesture = GestureType.SHAKA

        with patch.object(
            scene,
            "_do_capture",
            side_effect=lambda: setattr(scene, "current_box_pos_idx", 2),
        ):
            # VICTORY should be ignored now
            scene.update([mock_victory], [], 10.0)
            self.assertEqual(scene.stage, Projector3DCalibStage.PLACE_BOX)

            # Reset cooldown state for test
            scene._can_gesture = True

            # SHAKA should work
            scene.update([mock_shaka], [], 11.0)
            self.assertEqual(scene.stage, Projector3DCalibStage.CAPTURING)
            scene.update([], [], 12.0)
            self.assertEqual(scene.current_box_pos_idx, 2)

    def test_layer_rendering_no_crash(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        scene.on_enter()
        # This will call _update_layer_markers which sets instructions

        # Manually trigger a render update
        patches = scene.pattern_layer._generate_patches(1.0)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0].data.shape[2], 4)  # Should be BGRA

    def test_get_active_layers(self):
        scene = Projector3DCalibrationScene(self.mock_context)
        mock_app = MagicMock()
        mock_app.notification_layer = MagicMock()
        mock_app.cursor_layer = MagicMock()

        layers = scene.get_active_layers(mock_app)
        self.assertIn(scene.pattern_layer, layers)
        self.assertIn(scene.feedback_layer, layers)
        self.assertIn(mock_app.notification_layer, layers)
        self.assertIn(mock_app.cursor_layer, layers)
        # Menu layer should NOT be here
        self.assertNotIn(getattr(mock_app, "menu_layer", None), layers)


if __name__ == "__main__":
    unittest.main()
