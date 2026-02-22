import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.vision.input_processor import InputProcessor
from light_map.common_types import AppConfig, GmPosition, GestureType


@pytest.fixture
def config():
    return AppConfig(
        width=1000, height=1000, projector_matrix=np.eye(3), gm_position=GmPosition.NONE
    )


def test_convert_mediapipe_to_inputs_filtering(config):
    processor = InputProcessor(config)

    # Mock MediaPipe results
    results = MagicMock()

    landmark = MagicMock()
    landmark.x = 0.8  # 800 in 1000x1000
    landmark.y = 0.8  # 800 in 1000x1000

    # MediaPipe landmarks list
    hand_landmarks = MagicMock()
    hand_landmarks.landmark = [landmark] * 21  # Index tip is at 8

    results.multi_hand_landmarks = [hand_landmarks]

    # Handedness
    handedness = MagicMock()
    handedness.classification = [MagicMock(label="Left")]
    results.multi_handedness = [handedness]

    # Mock detect_gesture
    import light_map.vision.input_processor as ip

    ip.detect_gesture = MagicMock(return_value=GestureType.OPEN_PALM)

    # 1. No filtering
    inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
    assert len(inputs) == 1

    # 2. Filter North (should mask South, i.e., y > 500)
    # 800, 800 is South.
    config.gm_position = GmPosition.NORTH
    inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
    assert len(inputs) == 0

    # 3. Filter South (should NOT mask South, i.e., y > 500 is unmasked)
    config.gm_position = GmPosition.SOUTH
    inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
    assert len(inputs) == 1
