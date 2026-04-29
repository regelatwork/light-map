from unittest.mock import ANY, MagicMock, patch

import numpy as np
import pytest

from light_map.calibration.calibration_scenes import (
    FlashCalibrationScene,
    FlashCalibStage,
)
from light_map.core.app_context import AppContext
from light_map.core.common_types import AppConfig, CalibrationState, SceneId
from light_map.core.scene import SceneTransition
from light_map.state.temporal_event_manager import TemporalEventManager


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)
    mock_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_context.state = MagicMock()
    mock_context.state.calibration = CalibrationState()

    # Use a mutable object to hold time
    class TimeState:
        val = 0.0

    time_state = TimeState()

    def mock_monotonic():
        return time_state.val

    mock_context.time_provider = mock_monotonic
    mock_context.events = TemporalEventManager(time_provider=mock_monotonic)
    mock_context.time_state = time_state

    # Configure nested mocks
    mock_context.map_config_manager = MagicMock()
    mock_context.notifications = MagicMock()
    mock_context.map_system = MagicMock()
    return mock_context


def test_flash_calibration_scene_state_machine(mock_app_context):
    """Verify the state machine transitions and logic of the FlashCalibrationScene."""
    scene = FlashCalibrationScene(mock_app_context)
    time_state = mock_app_context.time_state

    with patch("time.monotonic", side_effect=mock_app_context.time_provider):
        with patch.object(scene.token_tracker, "detect_tokens") as mock_detect_tokens:
            # Simulate detection results
            # Instruction said set intensity to 255, so we expect 255.
            mock_detect_tokens.return_value = [MagicMock() for _ in range(5)]

            # Initial state
            scene.on_enter()
            assert scene._stage == FlashCalibStage.IDLE

            # IDLE -> FLASH (immediate transition in update)
            scene.update([], [], time_state.val)
            assert scene._stage == FlashCalibStage.FLASH
            assert mock_app_context.state.calibration.flash_intensity == 255
            assert (
                mock_app_context.state.calibration.instruction_text
                == "Flashing (Level 255)..."
            )

            # Iterate through test levels
            for i in range(len(scene._test_levels)):
                current_level = scene._test_levels[i]

                # Wait for FLASH timer (1.5s for each flash)
                time_state.val += 1.51
                mock_app_context.events.check()

                assert scene._stage == FlashCalibStage.FLASH
                assert scene._capture_frame is True
                assert (
                    mock_app_context.state.calibration.flash_intensity == current_level
                )

                # Update to trigger capture and process
                scene.update([], [], time_state.val)
                assert mock_detect_tokens.call_count == i + 1

                # Verify detect_tokens uses the correct frame from context
                mock_detect_tokens.assert_called_with(
                    frame_white=ANY,
                    projector_matrix=ANY,
                    map_system=mock_app_context.map_system,
                    default_height_mm=0.0,
                )
                # Capture frame should be reset after processing
                assert scene._capture_frame is False

                if i < len(scene._test_levels) - 1:
                    # FLASH -> COOLDOWN
                    assert scene._stage == FlashCalibStage.COOLDOWN
                    assert mock_app_context.state.calibration.flash_intensity == 0
                    assert (
                        mock_app_context.state.calibration.instruction_text
                        == "Cooldown..."
                    )

                    # COOLDOWN -> FLASH (via timer)
                    time_state.val += 0.51
                    mock_app_context.events.check()
                    assert scene._stage == FlashCalibStage.FLASH
                    assert (
                        mock_app_context.state.calibration.flash_intensity
                        == scene._test_levels[i + 1]
                    )

            # After all levels tested, should transition to ANALYZING
            assert scene._stage == FlashCalibStage.ANALYZING
            assert mock_app_context.state.calibration.instruction_text == "Analyzing..."

            # ANALYZING -> SHOW_RESULT
            time_state.val += 0.1
            scene.update([], [], time_state.val)
            assert scene._stage == FlashCalibStage.SHOW_RESULT
            assert (
                mock_app_context.state.calibration.instruction_text
                == "Optimal intensity found: 165"
            )

            # Optimal intensity for [255, 225, 195, 165, 135, 105, 75, 45] is 165 (median of sorted)
            mock_app_context.map_config_manager.set_flash_intensity.assert_called_once_with(
                165
            )
            mock_app_context.notifications.add_notification.assert_called_once_with(
                "Optimal intensity found: 165"
            )

            # SHOW_RESULT -> DONE (after delay)
            time_state.val += 2.01
            mock_app_context.events.check()
            assert scene._stage == FlashCalibStage.DONE

            transition = scene.update([], [], time_state.val)
            assert isinstance(transition, SceneTransition)
            assert transition.target_scene == SceneId.MENU


def test_flash_calibration_layers(mock_app_context):
    """Verify that the scene returns the correct layers for each stage."""
    scene = FlashCalibrationScene(mock_app_context)
    mock_app = MagicMock()

    scene._stage = FlashCalibStage.FLASH
    layers = scene.get_active_layers(mock_app)
    assert layers == [mock_app.flash_layer]

    scene._stage = FlashCalibStage.IDLE
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers

    scene._stage = FlashCalibStage.COOLDOWN
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers

    scene._stage = FlashCalibStage.DONE
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.cursor_layer in layers


def test_debug_mode_propagation(mock_app_context):
    """Verify that debug mode is propagated to TokenTracker."""
    mock_app_context.debug_mode = True
    scene = FlashCalibrationScene(mock_app_context)

    # Use its own events mock since we are not using the fixture's complex one here
    scene.context.events = MagicMock()

    scene.on_enter()
    assert scene.token_tracker.debug_mode is True
