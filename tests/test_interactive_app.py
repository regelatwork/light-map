import pytest
import numpy as np
from unittest.mock import MagicMock
from src.light_map.interactive_app import InteractiveApp, AppConfig
from src.light_map.common_types import MenuItem, MenuActions, GestureType
from src.light_map.menu_config import ROOT_MENU
from src.light_map.gestures import detect_gesture # We need to mock this or rely on it

# Mock MediaPipe Results
class MockHandLandmark:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z

class MockResults:
    def __init__(self, landmarks=None, label="Right"):
        if landmarks:
            self.multi_hand_landmarks = [MagicMock(landmark=landmarks)]
            classification = MagicMock()
            classification.label = label
            self.multi_handedness = [MagicMock(classification=[classification])]
        else:
            self.multi_hand_landmarks = None
            self.multi_handedness = None

@pytest.fixture
def app_config():
    # Identity matrix for simplicity: Camera (x,y) -> Projector (x,y)
    matrix = np.eye(3, dtype=np.float32)
    return AppConfig(width=100, height=100, projector_matrix=matrix, root_menu=ROOT_MENU)

def test_interactive_app_initialization(app_config):
    app = InteractiveApp(app_config)
    assert app is not None
    assert app.menu_system is not None

def test_process_frame_no_hands(app_config):
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults(landmarks=None)
    
    output, actions = app.process_frame(frame, results)
    
    assert output.shape == (100, 100, 3)
    assert len(actions) == 0
    # Should be mostly black (plus debug text overlay which is non-zero)
    # Testing exact pixels is brittle, but we know it runs.

def test_process_frame_with_hand(app_config):
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Create landmarks for an open palm (all fingers extended)
    # Wrist at 0,0
    # Tips far from wrist
    landmarks = [MockHandLandmark(0.5, 0.5)] * 21
    # Hack: We can mock detect_gesture to return a known gesture instead of building complex landmarks
    
    with pytest.MonkeyPatch.context() as m:
        # Mock detect_gesture to return VICTORY
        m.setattr("src.light_map.interactive_app.detect_gesture", lambda lm, label: GestureType.VICTORY)
        
        # Mock index finger tip (id 8) to be at 0.5, 0.5 -> 50, 50
        landmarks[8] = MockHandLandmark(0.5, 0.5) 
        
        results = MockResults(landmarks=landmarks)
        
        output, actions = app.process_frame(frame, results)
        
        # Verify state update
        # Since we sent VICTORY, and app uses it for SUMMON
        # The menu state should respond (start summoning).
        # We can't easily peek inside without breaking encapsulation, 
        # but we can check if output changes over time or if internal state changed.
        
        assert app.input_manager.get_gesture() == GestureType.VICTORY
        assert app.input_manager.get_x() == 50
        assert app.input_manager.get_y() == 50

def test_coordinate_transformation(app_config):
    # Set a translation matrix: x -> x+10, y -> y+20
    matrix = np.eye(3, dtype=np.float32)
    matrix[0, 2] = 10
    matrix[1, 2] = 20
    app_config.projector_matrix = matrix
    
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Hand at 0.1, 0.1 -> 10, 10 in camera space
    landmarks = [MockHandLandmark(0, 0)] * 21
    landmarks[8] = MockHandLandmark(0.1, 0.1) # Index tip
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.light_map.interactive_app.detect_gesture", lambda lm, label: GestureType.OPEN_PALM)
        results = MockResults(landmarks=landmarks)
        
        app.process_frame(frame, results)
        
        # Expected: 10 + 10 = 20, 10 + 20 = 30
        assert app.input_manager.get_x() == 20
        assert app.input_manager.get_y() == 30
