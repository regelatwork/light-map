import pytest
from light_map.dwell_tracker import DwellTracker
from light_map.vision.input_processor import InputProcessor, DummyResults
from light_map.common_types import AppConfig, GestureType
import numpy as np


def test_dwell_tracker_basic():
    # 10 pixel radius, 2 second threshold
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0)
    
    # First update
    assert tracker.update((100, 100), 0.5) is False
    assert tracker.accumulated_time == 0.0
    
    # Stable update
    assert tracker.update((102, 102), 1.0) is False
    assert tracker.accumulated_time == 1.0
    
    # Reached threshold
    assert tracker.update((101, 99), 1.1) is True
    assert tracker.accumulated_time == 2.1
    assert tracker.is_triggered is True
    
    # Subsequent stable updates shouldn't re-trigger
    assert tracker.update((100, 100), 0.5) is False


def test_dwell_tracker_reset():
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0)
    tracker.update((100, 100), 1.5)
    
    # Move outside radius
    assert tracker.update((120, 120), 0.1) is False
    assert tracker.accumulated_time == 0.0
    assert tracker.last_point == (120, 120)


def test_input_processor_virtual_pointer_offset(mocker):
    # Mock config
    config = mocker.Mock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    config.projector_matrix = np.eye(3)
    config.projector_ppi = 100.0 # 100 pixels per inch
    config.distortion_model = None
    config.gm_position = "None"
    
    processor = InputProcessor(config)
    
    # Create dummy landmarks for POINTING
    # Index finger PIP at (0.5, 0.5), Tip at (0.5, 0.4) -> pointing UP in cam space
    landmarks = [ {"x": 0.0, "y": 0.0} ] * 21
    landmarks[6] = {"x": 0.5, "y": 0.5} # PIP
    landmarks[8] = {"x": 0.5, "y": 0.4} # TIP
    
    results = DummyResults([landmarks], [{"label": "Right", "score": 1.0}])
    
    # Mock detect_gesture to return POINTING
    mocker.patch("light_map.vision.input_processor.detect_gesture", return_value=GestureType.POINTING)
    
    inputs = processor.convert_mediapipe_to_inputs(results, (1080, 1920, 3))
    
    assert len(inputs) == 1
    inp = inputs[0]
    
    # Tip at (0.5, 0.4) maps to (960, 432) in 1920x1080
    assert inp.proj_pos == (960, 432)
    
    # Pointer should be offset UP by 100 pixels (since pointing UP)
    # Cursor should be at (960, 332)
    assert inp.cursor_pos[0] == 960
    assert inp.cursor_pos[1] < 432
    # Check if distance is approx PPI
    dist = np.sqrt((inp.cursor_pos[0] - inp.proj_pos[0])**2 + (inp.cursor_pos[1] - inp.proj_pos[1])**2)
    assert pytest.approx(dist, abs=2) == 100.0
