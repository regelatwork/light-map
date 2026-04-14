import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.vision.processing.input_processor import InputProcessor
from light_map.core.common_types import AppConfig, GestureType


@pytest.fixture
def config():
    return AppConfig(
        width=1000,
        height=1000,
        projector_matrix=np.eye(3),
        projector_ppi=100.0,
        pointer_offset_mm=0.0, # Disable offset for simple extension test
    )


def test_pointer_extension_calculation(config):
    processor = InputProcessor(config)

    # Mock MediaPipe results
    results = MagicMock()

    # We need 21 landmarks
    landmarks = [MagicMock() for _ in range(21)]
    # Index PIP (6) at (0.5, 0.5)
    landmarks[6].x = 0.5
    landmarks[6].y = 0.5
    # Index TIP (8) at (0.5, 0.4) -> Pointing UP in camera space
    landmarks[8].x = 0.5
    landmarks[8].y = 0.4

    hand_landmarks = MagicMock()
    hand_landmarks.landmark = landmarks
    results.multi_hand_landmarks = [hand_landmarks]

    handedness = MagicMock()
    handedness.classification = [MagicMock(label="Right")]
    results.multi_handedness = [handedness]

    # Mock detect_gesture to return POINTING
    import light_map.vision.processing.input_processor as ip

    original_detect = ip.detect_gesture
    ip.detect_gesture = MagicMock(return_value=GestureType.POINTING)

    try:
        # 1. Default extension (2.0 inches)
        inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
        assert len(inputs) == 1
        hi = inputs[0]

        # px, py should be (500, 400) because tip is at (0.5, 0.4)
        assert hi.proj_pos == (500, 400)

        # Direction should be (0, -1) because TIP is above PIP
        assert hi.unit_direction[0] == pytest.approx(0.0)
        assert hi.unit_direction[1] == pytest.approx(-1.0)

        # cursor_pos = proj_pos + direction * ppi * extension - offset
        # px = 500, py = 400, dir=(0, -1), ppi=100, extension=2
        # cx = 500 + 0 * 100 * 2 = 500
        # cy = 400 + (-1) * 100 * 2 = 200
        assert hi.cursor_pos == (500, 200)

        # 2. Custom extension (3.0 inches)
        config.pointer_extension_inches = 3.0
        inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
        hi = inputs[0]
        # cy = 400 + (-1) * 100 * 3 = 100
        assert hi.cursor_pos == (500, 100)

        # 3. Zero extension
        config.pointer_extension_inches = 0.0
        inputs = processor.convert_mediapipe_to_inputs(results, (1000, 1000, 3))
        hi = inputs[0]
        # cy = 400 + (-1) * 100 * 0 = 400
        assert hi.cursor_pos == (500, 400)

    finally:
        ip.detect_gesture = original_detect
