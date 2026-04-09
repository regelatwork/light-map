import pytest
from light_map.input.gestures import is_finger_extended, detect_gesture


class MockLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y


@pytest.fixture
def mock_hand():
    """Returns a list of 21 MockLandmarks initialized to (0.5, 0.5)."""
    return [MockLandmark(0.5, 0.5) for _ in range(21)]


def test_is_finger_extended_index_open(mock_hand):
    # Simulate an open index finger (pointing up)
    mock_hand[0] = MockLandmark(0.5, 1.0)  # Wrist
    mock_hand[6] = MockLandmark(0.5, 0.6)  # Index PIP
    mock_hand[8] = MockLandmark(0.5, 0.4)  # Index Tip (Higher than PIP)

    assert is_finger_extended(mock_hand, "Index")


def test_is_finger_extended_index_closed(mock_hand):
    # Simulate a closed index finger
    mock_hand[0] = MockLandmark(0.5, 1.0)  # Wrist
    mock_hand[6] = MockLandmark(0.5, 0.6)  # PIP
    mock_hand[8] = MockLandmark(0.5, 0.7)  # Tip (Lower than PIP)

    assert not is_finger_extended(mock_hand, "Index")


def test_detect_gesture_open_palm(mock_hand):
    # Wrist
    mock_hand[0] = MockLandmark(0.5, 1.0)

    # Thumb: Extended (Tip far from Pinky MCP)
    mock_hand[17] = MockLandmark(0.9, 0.5)  # Pinky MCP
    mock_hand[5] = MockLandmark(0.5, 0.5)  # Index MCP
    mock_hand[4] = MockLandmark(0.1, 0.5)  # Tip (Far Left)
    mock_hand[3] = MockLandmark(0.4, 0.5)  # IP

    # Fingers: Extended (Tip higher than PIP)
    finger_indices = [(8, 6), (12, 10), (16, 14), (20, 18)]
    for tip_idx, pip_idx in finger_indices:
        mock_hand[tip_idx] = MockLandmark(0.5, 0.1)  # Far Up
        mock_hand[pip_idx] = MockLandmark(0.5, 0.5)  # Mid

    assert detect_gesture(mock_hand, "Right") == "Open Palm"


def test_detect_gesture_closed_fist(mock_hand):
    # Wrist
    mock_hand[0] = MockLandmark(0.5, 1.0)

    # Thumb: Closed
    mock_hand[17] = MockLandmark(0.9, 0.5)
    mock_hand[5] = MockLandmark(0.5, 0.5)
    mock_hand[4] = MockLandmark(0.8, 0.5)  # Tip near Pinky MCP
    mock_hand[3] = MockLandmark(0.7, 0.5)

    # Fingers: Closed (Tip lower than PIP)
    finger_indices = [(8, 6), (12, 10), (16, 14), (20, 18)]
    for tip_idx, pip_idx in finger_indices:
        mock_hand[tip_idx] = MockLandmark(0.5, 0.9)  # Near Wrist
        mock_hand[pip_idx] = MockLandmark(0.5, 0.5)  # Mid

    assert detect_gesture(mock_hand, "Right") == "Closed Fist"


def test_detect_gesture_gun(mock_hand):
    # Wrist
    mock_hand[0] = MockLandmark(0.5, 1.0)
    mock_hand[17] = MockLandmark(0.9, 0.5)
    mock_hand[5] = MockLandmark(0.5, 0.5)

    # Thumb: Open
    mock_hand[4] = MockLandmark(0.1, 0.5)
    mock_hand[3] = MockLandmark(0.4, 0.5)

    # Index: Open
    mock_hand[8] = MockLandmark(0.5, 0.1)
    mock_hand[6] = MockLandmark(0.5, 0.5)

    # Others: Closed
    for tip_idx, pip_idx in [(12, 10), (16, 14), (20, 18)]:
        mock_hand[tip_idx] = MockLandmark(0.5, 0.9)
        mock_hand[pip_idx] = MockLandmark(0.5, 0.5)

    assert detect_gesture(mock_hand, "Right") == "Gun"


def test_detect_gesture_pointing(mock_hand):
    # Wrist
    mock_hand[0] = MockLandmark(0.5, 1.0)
    mock_hand[17] = MockLandmark(0.9, 0.5)
    mock_hand[5] = MockLandmark(0.5, 0.5)

    # Thumb: Closed
    mock_hand[4] = MockLandmark(0.8, 0.5)
    mock_hand[3] = MockLandmark(0.7, 0.5)

    # Index: Open
    mock_hand[8] = MockLandmark(0.5, 0.1)
    mock_hand[6] = MockLandmark(0.5, 0.5)

    # Others: Closed
    for tip_idx, pip_idx in [(12, 10), (16, 14), (20, 18)]:
        mock_hand[tip_idx] = MockLandmark(0.5, 0.9)
        mock_hand[pip_idx] = MockLandmark(0.5, 0.5)

    assert detect_gesture(mock_hand, "Right") == "Pointing"


def test_detect_gesture_tucked_thumb_not_gun(mock_hand):
    # Wrist
    mock_hand[0] = MockLandmark(0.5, 1.0)
    mock_hand[17] = MockLandmark(0.9, 0.5)
    mock_hand[5] = MockLandmark(0.5, 0.8)  # Index MCP (Lower)

    # Thumb: Tucked (close to index finger)
    mock_hand[4] = MockLandmark(0.55, 0.7)
    mock_hand[3] = MockLandmark(0.6, 0.6)

    # Index: Open
    mock_hand[8] = MockLandmark(0.5, 0.1)
    mock_hand[6] = MockLandmark(0.5, 0.5)

    # Others: Closed
    for tip_idx, pip_idx in [(12, 10), (16, 14), (20, 18)]:
        mock_hand[tip_idx] = MockLandmark(0.5, 0.9)
        mock_hand[pip_idx] = MockLandmark(0.5, 0.5)

    assert detect_gesture(mock_hand, "Right") == "Pointing"
