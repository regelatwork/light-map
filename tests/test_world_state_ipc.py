import numpy as np
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

    # 1. Apply ArUco result (Initial)
    tokens = [Token(id=1, world_x=10, world_y=20, grid_x=0, grid_y=0)]
    result = DetectionResult(
        timestamp=2000, type=ResultType.ARUCO, data={"tokens": tokens}
    )

    state.apply(result)
    assert len(state.tokens) == 1
    assert state.dirty_tokens is True
    state.clear_dirty()

    # 2. Apply SAME tokens again - should NOT be dirty
    result_same = DetectionResult(
        timestamp=2010, type=ResultType.ARUCO, data={"tokens": tokens}
    )
    state.apply(result_same)
    assert state.dirty_tokens is False

    # 3. Apply tokens with tiny jitter (< 0.01) - should NOT be dirty
    jitter_tokens = [Token(id=1, world_x=10.005, world_y=20.0, grid_x=0, grid_y=0)]
    result_jitter = DetectionResult(
        timestamp=2020, type=ResultType.ARUCO, data={"tokens": jitter_tokens}
    )
    state.apply(result_jitter)
    assert state.dirty_tokens is False

    # 4. Apply tokens with significant movement - SHOULD be dirty
    moved_tokens = [Token(id=1, world_x=15.0, world_y=20.0, grid_x=0, grid_y=0)]
    result_moved = DetectionResult(
        timestamp=2030, type=ResultType.ARUCO, data={"tokens": moved_tokens}
    )
    state.apply(result_moved)
    assert state.dirty_tokens is True
    state.clear_dirty()

    # 5. Apply tokens with grid change - SHOULD be dirty
    grid_tokens = [Token(id=1, world_x=10.0, world_y=20.0, grid_x=1, grid_y=0)]
    result_grid = DetectionResult(
        timestamp=2040, type=ResultType.ARUCO, data={"tokens": grid_tokens}
    )
    state.apply(result_grid)
    assert state.dirty_tokens is True
    state.clear_dirty()

    # 6. Apply ArUco result (Raw corners) - SHOULD dirty tokens for calibration updates
    raw_data = {"corners": [[[0, 0], [1, 0], [1, 1], [0, 1]]], "ids": [42]}
    result_raw = DetectionResult(timestamp=2050, type=ResultType.ARUCO, data=raw_data)
    state.apply(result_raw)
    assert state.raw_aruco["ids"] == [42]
    assert state.dirty_tokens is True
    state.clear_dirty()

    # 7. Apply both Snapped and Raw tokens
    # If snapped tokens are same, but raw tokens are different -> dirty_tokens should be FALSE
    tokens = [Token(id=1, world_x=75.0, world_y=125.0, grid_x=1, grid_y=2)]
    raw_tokens = [Token(id=1, world_x=73.0, world_y=122.0)]  # jittery

    state.tokens = tokens
    state.raw_tokens = []
    state.clear_dirty()

    result_both = DetectionResult(
        timestamp=2060,
        type=ResultType.ARUCO,
        data={"tokens": tokens, "raw_tokens": raw_tokens},
    )
    state.apply(result_both)

    assert state.raw_tokens == raw_tokens
    assert state.dirty_tokens is False  # NO DIRTY because snapped tokens didn't move

    # 8. If snapped tokens DO move -> dirty_tokens should be TRUE
    tokens_moved = [Token(id=1, world_x=125.0, world_y=125.0, grid_x=2, grid_y=2)]
    result_moved = DetectionResult(
        timestamp=2070,
        type=ResultType.ARUCO,
        data={"tokens": tokens_moved, "raw_tokens": raw_tokens},
    )
    state.apply(result_moved)
    assert state.dirty_tokens is True

    state.clear_dirty()
    assert state.is_dirty is False

    # Apply Hands result
    result_hands = DetectionResult(
        timestamp=2100, type=ResultType.HANDS, data={"landmarks": [0.5, 0.5]}
    )
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
