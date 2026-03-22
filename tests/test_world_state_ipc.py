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
    assert state.last_frame_timestamp == 1000


def test_world_state_apply_results():
    state = WorldState()

    # 1. Apply ArUco result (Initial)
    tokens = [Token(id=1, world_x=10, world_y=20)]
    result = DetectionResult(
        timestamp=2000, type=ResultType.ARUCO, data={"tokens": tokens}
    )

    last_ts = state.tokens_version
    state.apply(result)
    assert len(state.tokens) == 1
    assert state.tokens_version > last_ts
    last_ts = state.tokens_version

    # 2. Apply SAME tokens again - should NOT increment version
    result_same = DetectionResult(
        timestamp=2010, type=ResultType.ARUCO, data={"tokens": tokens}
    )
    state.apply(result_same)
    assert state.tokens_version == last_ts

    # 3. Apply tokens with tiny jitter (< 0.01) - should NOT increment version
    jitter_tokens = [Token(id=1, world_x=10.005, world_y=20.0)]
    result_jitter = DetectionResult(
        timestamp=2020, type=ResultType.ARUCO, data={"tokens": jitter_tokens}
    )
    state.apply(result_jitter)
    assert state.tokens_version == last_ts

    # 4. Apply tokens with significant movement - SHOULD increment version
    moved_tokens = [Token(id=1, world_x=15.0, world_y=20.0)]
    result_moved = DetectionResult(
        timestamp=2030, type=ResultType.ARUCO, data={"tokens": moved_tokens}
    )
    state.apply(result_moved)
    assert state.tokens_version > last_ts
    last_ts = state.tokens_version

    # 5. Apply tokens with grid change - SHOULD increment version
    grid_tokens = [Token(id=1, world_x=10.0, world_y=20.0, grid_x=1, grid_y=0)]
    result_grid = DetectionResult(
        timestamp=2040, type=ResultType.ARUCO, data={"tokens": grid_tokens}
    )
    state.apply(result_grid)
    assert state.tokens_version > last_ts
    last_ts = last_ts = state.tokens_version  # Actually I'll just keep the structure

    # 6. Apply ArUco result (Raw corners) - SHOULD increment raw_aruco_version
    raw_data = {"corners": [[[0, 0], [1, 0], [1, 1], [0, 1]]], "ids": [42]}
    result_raw = DetectionResult(timestamp=2050, type=ResultType.ARUCO, data=raw_data)
    last_raw_ts = state.raw_aruco_version
    state.apply(result_raw)
    assert state.raw_aruco["ids"] == [42]
    assert state.raw_aruco_version > last_raw_ts
    # Should NOT increment tokens_version
    assert state.tokens_version == last_ts
    last_ts = state.tokens_version

    # 7. Apply both Snapped and Raw tokens
    # If snapped tokens are same, but raw tokens are different -> tokens_version should increment
    tokens = [Token(id=1, world_x=75.0, world_y=125.0, grid_x=1, grid_y=2)]
    raw_tokens = [Token(id=1, world_x=73.0, world_y=122.0)]

    state.tokens = tokens
    state.raw_tokens = []
    # Sync timestamp to known state
    last_ts = state.tokens_version

    result_both = DetectionResult(
        timestamp=2060,
        type=ResultType.ARUCO,
        data={"tokens": tokens, "raw_tokens": raw_tokens},
    )
    state.apply(result_both)

    assert state.raw_tokens == raw_tokens
    assert state.tokens_version > last_ts  # Updated because raw_tokens changed
    last_ts = state.tokens_version

    # 8. If nothing changed (both snapped and raw) -> tokens_version should NOT increment
    result_no_change = DetectionResult(
        timestamp=2070,
        type=ResultType.ARUCO,
        data={"tokens": tokens, "raw_tokens": raw_tokens},
    )
    state.apply(result_no_change)
    assert state.tokens_version == last_ts

    # Apply Hands result
    result_hands = DetectionResult(
        timestamp=2100, type=ResultType.HANDS, data={"landmarks": [0.5, 0.5]}
    )
    state.apply(result_hands)
    assert state.hands_version > 0


def test_world_state_apply_actions():
    state = WorldState()

    # 1. Apply Action result
    action_data = {"action": "SYNC_VISION", "payload": None}
    result = DetectionResult(timestamp=3000, type=ResultType.ACTION, data=action_data)

    state.apply(result)
    assert len(state.pending_actions) == 1
    assert state.pending_actions[0] == action_data

    # 2. Apply another one
    action_data_2 = {"action": "ZOOM", "delta": 0.1}
    result_2 = DetectionResult(
        timestamp=3010, type=ResultType.ACTION, data=action_data_2
    )

    state.apply(result_2)
    assert len(state.pending_actions) == 2
    assert state.pending_actions[1] == action_data_2


def test_world_state_timestamp_sync():
    state = WorldState()
    state.last_frame_timestamp = 5000

    # Old frame should be ignored
    old_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    state.update_from_frame(old_frame, 4000)

    assert state.background is None
    assert state.last_frame_timestamp == 5000
