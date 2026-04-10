import pytest
from unittest.mock import MagicMock, patch, ANY
import numpy as np

from light_map.core.app_context import AppContext
from light_map.calibration.calibration_scenes import (
    FlashCalibrationScene,
    FlashCalibStage,
)
from light_map.core.common_types import AppConfig, SceneId
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
            # Simulate detection results for each level
            # For simplicity, let's say it finds 5 tokens for intensity 105, else 0
            def side_effect_detect_tokens(*args, **kwargs):
                current_intensity = scene._test_levels[scene._current_level_idx]
                if current_intensity == 105:
                    return [MagicMock() for _ in range(5)]  # 5 tokens
                return []  # 0 tokens

            mock_detect_tokens.side_effect = side_effect_detect_tokens

            # Initial state
            scene.on_enter()
            assert scene._stage == FlashCalibStage.START

            # START -> TESTING
            time_state.val += 0.1
            scene.update([], [], time_state.val)
            assert scene._stage == FlashCalibStage.TESTING

            # Iterate through test levels
            for i, intensity in enumerate(scene._test_levels):
                # Settle time
                time_state.val += 1.51
                mock_app_context.events.check()
                assert scene._stage == FlashCalibStage.TESTING
                assert scene._capture_frame is True

                # Render to trigger capture and process
                scene.render(np.zeros((100, 100, 3), dtype=np.uint8))
                assert mock_detect_tokens.call_count == i + 1

                # Verify detect_tokens uses the correct frame from context
                mock_detect_tokens.assert_called_with(
                    frame_white=ANY,
                    projector_matrix=ANY,
                    map_system=mock_app_context.map_system,
                    default_height_mm=0.0,
                )
                # Capture frame should be reset after render
                assert scene._capture_frame is False

            # After all levels tested, should transition to ANALYZING
            assert scene._stage == FlashCalibStage.ANALYZING

            # ANALYZING -> SHOW_RESULT
            time_state.val += 0.1
            scene.update([], [], time_state.val)
            assert scene._stage == FlashCalibStage.SHOW_RESULT
            mock_app_context.map_config_manager.set_flash_intensity.assert_called_once_with(
                105
            )
            mock_app_context.notifications.add_notification.assert_called_once_with(
                "Optimal intensity found: 105"
            )

            # SHOW_RESULT -> DONE (after delay)
            time_state.val += 2.01
            mock_app_context.events.check()
            assert scene._stage == FlashCalibStage.DONE

            transition = scene.update([], [], time_state.val)
            assert isinstance(transition, SceneTransition)
            assert transition.target_scene == SceneId.MENU


@patch("numpy.full_like")
def test_render_flash_levels(mock_full_like, mock_app_context):
    """Verify that the scene renders the correct flash intensity during testing."""
    scene = FlashCalibrationScene(mock_app_context)
    time_state = mock_app_context.time_state

    with patch("time.monotonic", side_effect=mock_app_context.time_provider):
        with patch.object(
            scene.token_tracker, "detect_tokens"
        ):  # Don't care about detection here
            scene.on_enter()
            scene.update([], [], time_state.val)

            for i in range(len(scene._test_levels) - 1):
                # Advance time and check events to trigger capture_frame
                time_state.val += 1.51
                mock_app_context.events.check()

                frame = np.zeros((100, 100, 3), dtype=np.uint8)
                scene.render(frame)

                # The render method uses the intensity for the *next* level for display
                expected_intensity_for_display = scene._test_levels[i + 1]

                mock_full_like.assert_called_with(
                    ANY, expected_intensity_for_display, dtype=np.uint8
                )
                mock_full_like.reset_mock()

            # Handle the last test level separately
            time_state.val += 1.51
            mock_app_context.events.check()

            frame = np.zeros((100, 100, 3), dtype=np.uint8)
            scene.render(frame)

            # After processing the last level, render transitions to ANALYZING
            # and should return a black frame. np.full_like should *not* be called
            # for the display of the last level.
            mock_full_like.assert_not_called()


def test_debug_mode_propagation(mock_app_context):
    """Verify that debug mode is propagated to TokenTracker."""
    mock_app_context.debug_mode = True
    scene = FlashCalibrationScene(mock_app_context)

    # Use its own events mock since we are not using the fixture's complex one here if we don't want to
    scene.context.events = MagicMock()

    scene.on_enter()
    assert scene.token_tracker.debug_mode is True
