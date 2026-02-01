import pytest
from unittest.mock import MagicMock
from src.light_map.input_manager import InputManager
from src.light_map.common_types import GestureType

# Mock Data Structures
class MockLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class MockHandLandmarks:
    def __init__(self, landmarks):
        self.landmark = landmarks

class MockClassification:
    def __init__(self, label):
        self.label = label

class MockHandedness:
    def __init__(self, label):
        self.classification = [MockClassification(label)]

class MockResults:
    def __init__(self, multi_hand_landmarks, multi_handedness):
        self.multi_hand_landmarks = multi_hand_landmarks
        self.multi_handedness = multi_handedness

def create_mock_hand(label="Right", x=0.5, y=0.5):
    # create 21 landmarks
    landmarks = [MockLandmark(x, y) for _ in range(21)]
    # Modify specific landmarks to simulate "Open Palm" (all extended)
    # Wrist is 0
    # Tips are 4, 8, 12, 16, 20
    # PIPs are 3, 6, 10, 14, 18
    # To be "Open Palm", tip distance to wrist > pip distance to wrist
    # We can just mock the detect_gesture function? 
    # Or just rely on the fact that identical coords might produce something.
    # Actually, InputManager calls detect_gesture. 
    # To avoid complex landmark math in tests, we can mock detect_gesture import in InputManager?
    # Or just construct landmarks that satisfy "Open Palm".
    # Let's make tips far from wrist (0,0) and pips close.
    # Wrist at 0.5, 0.5. 
    # Tips at 0.9, 0.9. PIPs at 0.6, 0.6.
    landmarks[0] = MockLandmark(0.5, 0.5) # Wrist
    
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18] # Actually Thumb IP is 3, others are 6...
    
    # Set all tips far
    for idx in tips:
        landmarks[idx] = MockLandmark(0.9, 0.9)
    # Set all pips close
    for idx in pips:
        landmarks[idx] = MockLandmark(0.6, 0.6)
        
    # Except Thumb logic is complex. 
    # Let's just assume we get Open Palm if we do this, or just mock detect_gesture.
    # Mocking detect_gesture is safer for unit testing InputManager logic specifically.
    return MockHandLandmarks(landmarks), MockHandedness(label)

@pytest.fixture
def input_manager():
    return InputManager(flicker_timeout=0.5)

def test_sticky_hand_selection(input_manager):
    # Detect Right Hand
    hand_lm, hand_handedness = create_mock_hand("Right", 0.5, 0.5)
    results = MockResults([hand_lm], [hand_handedness])
    
    # Process t=0
    out = input_manager.process(results, timestamp=1.0, frame_shape=(100, 100, 3))
    assert out is not None
    assert input_manager.primary_hand_label == "Right"

    # Detect Left Hand
    hand_lm_l, hand_handedness_l = create_mock_hand("Left", 0.2, 0.2)
    results_l = MockResults([hand_lm_l], [hand_handedness_l])
    
    # Process t=1.1 (should switch if Right is missing? No, sticky logic)
    # But wait, if Right is MISSING from candidates, it checks timeout.
    # Here we present ONLY Left.
    out = input_manager.process(results_l, timestamp=1.1, frame_shape=(100, 100, 3))
    
    # Since 1.1 - 1.0 < 0.5 (timeout), it should return None (flicker recovery) 
    # because primary (Right) is missing but not timed out.
    assert out is None
    assert input_manager.primary_hand_label == "Right"

def test_sticky_hand_timeout(input_manager):
    # Detect Right Hand
    hand_lm, hand_handedness = create_mock_hand("Right", 0.5, 0.5)
    results = MockResults([hand_lm], [hand_handedness])
    input_manager.process(results, timestamp=1.0, frame_shape=(100, 100, 3))
    
    # Detect Left Hand after timeout
    hand_lm_l, hand_handedness_l = create_mock_hand("Left", 0.2, 0.2)
    results_l = MockResults([hand_lm_l], [hand_handedness_l])
    
    # Process t=2.0 (Diff 1.0 > 0.5)
    out = input_manager.process(results_l, timestamp=2.0, frame_shape=(100, 100, 3))
    
    assert out is not None
    # Should switch to Left
    assert input_manager.primary_hand_label == "Left"

def test_flicker_recovery_no_hands(input_manager):
    # Detect Right Hand
    hand_lm, hand_handedness = create_mock_hand("Right", 0.5, 0.5)
    results = MockResults([hand_lm], [hand_handedness])
    input_manager.process(results, timestamp=1.0, frame_shape=(100, 100, 3))
    
    # No hands
    results_empty = MockResults([], [])
    
    # Process t=1.1 (< timeout)
    out = input_manager.process(results_empty, timestamp=1.1, frame_shape=(100, 100, 3))
    assert out is None
    assert input_manager.primary_hand_label == "Right" # Still holding on
    
    # Process t=2.0 (> timeout)
    out = input_manager.process(results_empty, timestamp=2.0, frame_shape=(100, 100, 3))
    assert out is None
    assert input_manager.primary_hand_label is None # Dropped

def test_multi_hand_stickiness(input_manager):
    # Right and Left present
    h1, l1 = create_mock_hand("Right")
    h2, l2 = create_mock_hand("Left")
    
    results = MockResults([h1, h2], [l1, l2])
    
    # First detection, should pick first (Right)
    input_manager.process(results, timestamp=1.0, frame_shape=(100, 100, 3))
    assert input_manager.primary_hand_label == "Right"
    
    # Next frame, order swapped? MediaPipe often swaps order
    results_swapped = MockResults([h2, h1], [l2, l1])
    
    # Should still pick Right
    out = input_manager.process(results_swapped, timestamp=1.1, frame_shape=(100, 100, 3))
    assert out is not None
    # Verify it picked the Right hand (check coords/label logic if we could, 
    # but here we just check internal state)
    assert input_manager.primary_hand_label == "Right"
