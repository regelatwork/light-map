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


def test_pan_delta_closed_fist(map_interaction_controller, mock_map_system):
    """Verify that a single CLOSED_FIST gesture triggers panning."""
    # First update to establish the initial hand position
    inputs1 = [
        HandInput(
            gesture=GestureType.CLOSED_FIST, proj_pos=(100, 100), raw_landmarks=None
        )
    ]
    map_interaction_controller.process_gestures(inputs1, mock_map_system)
    mock_map_system.pan.assert_not_called()  # No pan on the first frame

    # Second update to calculate the delta
    inputs2 = [
        HandInput(
            gesture=GestureType.CLOSED_FIST, proj_pos=(120, 130), raw_landmarks=None
        )
    ]
    interaction_occurred = map_interaction_controller.process_gestures(
        inputs2, mock_map_system
    )

    assert interaction_occurred
    mock_map_system.pan.assert_called_once_with(20, 30)


def test_zoom_scaling_pointing(map_interaction_controller, mock_map_system):
    """Verify that two POINTING gestures trigger zooming."""
    # First update to establish the initial distance
    inputs1 = [
        HandInput(
            gesture=GestureType.POINTING, proj_pos=(100, 100), raw_landmarks=None
        ),
        HandInput(
            gesture=GestureType.POINTING, proj_pos=(200, 100), raw_landmarks=None
        ),
    ]
    map_interaction_controller.process_gestures(inputs1, mock_map_system)
    mock_map_system.zoom_pinned.assert_not_called()  # No zoom on the first frame

    # Second update to calculate the zoom factor (zooming in)
    inputs2 = [
        HandInput(gesture=GestureType.POINTING, proj_pos=(50, 100), raw_landmarks=None),
        HandInput(
            gesture=GestureType.POINTING, proj_pos=(250, 100), raw_landmarks=None
        ),
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


def test_no_interaction_wrong_gestures(map_interaction_controller, mock_map_system):
    """Verify that incorrect gestures do not trigger interactions."""
    # Case 1: One hand but wrong gesture (OPEN_PALM instead of CLOSED_FIST)
    inputs_wrong_pan = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(100, 100), raw_landmarks=None
        )
    ]
    assert (
        map_interaction_controller.process_gestures(inputs_wrong_pan, mock_map_system)
        is False
    )
    mock_map_system.pan.assert_not_called()

    # Case 2: Two hands but wrong gestures (OPEN_PALM instead of POINTING)
    inputs_wrong_zoom = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(100, 100), raw_landmarks=None
        ),
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(200, 100), raw_landmarks=None
        ),
    ]
    assert (
        map_interaction_controller.process_gestures(inputs_wrong_zoom, mock_map_system)
        is False
    )
    mock_map_system.zoom_pinned.assert_not_called()
