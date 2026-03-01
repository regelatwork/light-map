import numpy as np
import pytest
from light_map.core.world_state import WorldState
from light_map.common_types import DetectionResult, ResultType, Token

def test_world_state_roi_injection():
    # Define a mock ROI processor (crops 10x10)
    def mock_processor(frame):
        return frame[0:10, 0:10]
        
    state = WorldState(frame_processor=mock_processor)
    
    # Fake SHM view (100x100)
    full_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    full_frame[0, 0] = [255, 255, 255]
    
    state.update_from_frame(full_frame, 1000)
    
    assert state.background.shape == (10, 10, 3)
    assert np.array_equal(state.background[0, 0], [255, 255, 255])
    assert state.dirty_background is True
    assert state.is_dirty is True

def test_world_state_apply_results():
    state = WorldState()
    
    # Apply ArUco result
    tokens = [Token(id=1, world_x=10, world_y=20)]
    result = DetectionResult(timestamp=2000, type=ResultType.ARUCO, data={"tokens": tokens})
    
    state.apply(result)
    assert len(state.tokens) == 1
    assert state.dirty_tokens is True
    
    state.clear_dirty()
    assert state.is_dirty is False
    
    # Apply Hands result
    result_hands = DetectionResult(timestamp=2100, type=ResultType.HANDS, data={"landmarks": [0.5, 0.5]})
    state.apply(result_hands)
    assert state.dirty_hands is True
    assert state.is_dirty is True

def test_world_state_timestamp_sync():
    state = WorldState()
    state.last_frame_timestamp = 5000
    
    # Old frame should be ignored
    old_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    state.update_from_frame(old_frame, 4000)
    
    assert state.background is None
    assert state.last_frame_timestamp == 5000
    assert state.dirty_background is False
