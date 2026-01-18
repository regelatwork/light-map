import pytest
from src.light_map.gestures import is_finger_extended, detect_gesture

class MockLandmark:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def test_is_finger_extended_index_open():
    # Simulate an open index finger (pointing up)
    # Wrist at (0.5, 1.0), MCP at (0.5, 0.8), PIP at (0.5, 0.6), Tip at (0.5, 0.4)
    # Distance Tip-Wrist > PIP-Wrist
    
    landmarks = {}
    landmarks[0] = MockLandmark(0.5, 1.0) # Wrist
    landmarks[6] = MockLandmark(0.5, 0.6) # Index PIP
    landmarks[8] = MockLandmark(0.5, 0.4) # Index Tip
    
    # We pass a dictionary-like object that supports integer indexing?
    # The code expects a list or something indexable.
    
    l_list = [MockLandmark(0,0)] * 21
    l_list[0] = landmarks[0]
    l_list[6] = landmarks[6]
    l_list[8] = landmarks[8]
    
    assert is_finger_extended(l_list, "Index") == True

def test_is_finger_extended_index_closed():
    # Simulate a closed index finger
    # Tip is closer to wrist than PIP
    
    l_list = [MockLandmark(0,0)] * 21
    l_list[0] = MockLandmark(0.5, 1.0) # Wrist
    l_list[6] = MockLandmark(0.5, 0.6) # PIP
    l_list[8] = MockLandmark(0.5, 0.7) # Tip (lower than PIP, closer to wrist)
    
    assert is_finger_extended(l_list, "Index") == False

def test_detect_gesture_open_palm():
    # All fingers open
    # We need to construct a full hand of landmarks where tips are far from wrist
    l_list = [MockLandmark(0.5, 1.0)] * 21 # Wrist at bottom
    
    # Set Tips (4, 8, 12, 16, 20) to be far (y=0.0)
    # Set PIPs (3, 6, 10, 14, 18) to be mid (y=0.5)
    # Set Wrist to (0.5, 1.0)
    
    # Thumb (1-4). 3 is IP, 4 is Tip.
    # Thumb heuristic checks against Pinky MCP (17).
    # Let's place Pinky MCP at (0.9, 0.5)
    l_list[17] = MockLandmark(0.9, 0.5)
    
    # Open Thumb: Tip(4) is far from Pinky MCP(17). IP(3) is closer.
    l_list[4] = MockLandmark(0.1, 0.5) # Far left
    l_list[3] = MockLandmark(0.4, 0.5) # Closer to pinky
    
    # Other Fingers: Tip < PIP (y-wise, meaning higher on screen, further from wrist)
    wrist = l_list[0]
    
    finger_indices = [(8,6), (12,10), (16,14), (20,18)]
    for tip_idx, pip_idx in finger_indices:
        l_list[tip_idx] = MockLandmark(0.5, 0.1) # Far
        l_list[pip_idx] = MockLandmark(0.5, 0.5) # Mid
        
    assert detect_gesture(l_list, "Right") == "Open Palm"

def test_detect_gesture_closed_fist():
    # All fingers closed
    l_list = [MockLandmark(0.5, 1.0)] * 21
    l_list[17] = MockLandmark(0.9, 0.5) # Pinky MCP
    
    # Thumb Closed: Tip closer to Pinky MCP than IP?
    # Actually, thumb closed usually means tucked in.
    # Tip (0.8, 0.5) vs IP (0.7, 0.5)? 
    # Tip distance to Pinky MCP (0.9) = 0.1
    # IP distance to Pinky MCP (0.9) = 0.2
    # 0.1 < 0.2 -> False (Not Extended)
    l_list[4] = MockLandmark(0.8, 0.5)
    l_list[3] = MockLandmark(0.7, 0.5)
    
    # Other fingers: Tip closer to wrist than PIP
    wrist = l_list[0]
    finger_indices = [(8,6), (12,10), (16,14), (20,18)]
    for tip_idx, pip_idx in finger_indices:
        l_list[tip_idx] = MockLandmark(0.5, 0.9) # Near Wrist
        l_list[pip_idx] = MockLandmark(0.5, 0.5) # Mid
        
    assert detect_gesture(l_list, "Right") == "Closed Fist"
