import pytest
from unittest.mock import MagicMock
import numpy as np

from light_map.core.map_interaction import MapInteractionController
from light_map.core.scene import HandInput
from light_map.gestures import GestureType
from light_map.map_system import MapSystem


@pytest.fixture
def map_interaction_controller():
    return MapInteractionController()


@pytest.fixture
def mock_map_system():
    return MagicMock(spec=MapSystem)


def test_pan_delta(map_interaction_controller, mock_map_system):
    """Verify that a single open palm gesture produces the correct pan delta."""
    # First update to establish the initial hand position
    inputs1 = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(100, 100), raw_landmarks=None
        )
    ]
    map_interaction_controller.process_gestures(inputs1, mock_map_system)
    mock_map_system.pan.assert_not_called()  # No pan on the first frame

    # Second update to calculate the delta
    inputs2 = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(120, 130), raw_landmarks=None
        )
    ]
    interaction_occurred = map_interaction_controller.process_gestures(
        inputs2, mock_map_system
    )

    assert interaction_occurred
    mock_map_system.pan.assert_called_once_with(20, 30)


def test_zoom_scaling(map_interaction_controller, mock_map_system):
    """Verify that a two-hand gesture produces the correct zoom factor."""
    # First update to establish the initial distance
    inputs1 = [
        HandInput(gesture=GestureType.POINTING, proj_pos=(100, 100), raw_landmarks=None),
        HandInput(gesture=GestureType.POINTING, proj_pos=(200, 100), raw_landmarks=None),
    ]
    map_interaction_controller.process_gestures(inputs1, mock_map_system)
    mock_map_system.zoom_pinned.assert_not_called()  # No zoom on the first frame

    # Second update to calculate the zoom factor (zooming in)
    inputs2 = [
        HandInput(gesture=GestureType.POINTING, proj_pos=(50, 100), raw_landmarks=None),
        HandInput(gesture=GestureType.POINTING, proj_pos=(250, 100), raw_landmarks=None),
    ]
    interaction_occurred = map_interaction_controller.process_gestures(
        inputs2, mock_map_system
    )

    assert interaction_occurred
    # Initial distance was 100, new distance is 200. Factor should be 2.0
    mock_map_system.zoom_pinned.assert_called_once()
    args, _ = mock_map_system.zoom_pinned.call_args
    assert np.isclose(args[0], 2.0)  # scale_factor
    assert args[1] == (150, 100)  # center_point


def test_no_interaction_on_gesture_change(map_interaction_controller, mock_map_system):
    """Verify that changing gestures resets interaction state."""
    # Establish a panning hand
    inputs1 = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(100, 100), raw_landmarks=None
        )
    ]
    map_interaction_controller.process_gestures(inputs1, mock_map_system)

    # Change gesture
    inputs2 = [
        HandInput(gesture=GestureType.POINTING, proj_pos=(120, 130), raw_landmarks=None)
    ]
    interaction_occurred = map_interaction_controller.process_gestures(
        inputs2, mock_map_system
    )

    assert not interaction_occurred
    mock_map_system.pan.assert_not_called()
