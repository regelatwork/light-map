from light_map.core.world_state import WorldState
from light_map.common_types import DetectionResult, ResultType, Token, ViewportState


def test_world_state_timestamps_init():
    ws = WorldState()
    assert ws.map_timestamp > 0
    assert ws.menu_timestamp > 0
    assert ws.tokens_timestamp > 0
    assert ws.hands_timestamp > 0
    assert ws.notifications_timestamp > 0
    assert ws.viewport_timestamp > 0


def test_tokens_timestamp_increments():
    ws = WorldState()
    initial = ws.tokens_timestamp

    # Simulate a change in tokens
    tokens = [Token(id=1, world_x=10, world_y=20)]
    res = DetectionResult(timestamp=100, type=ResultType.ARUCO, data={"tokens": tokens})
    ws.apply(res)

    assert ws.tokens_timestamp > initial
    assert ws.tokens == tokens


def test_hands_timestamp_increments():
    ws = WorldState()
    initial = ws.hands_timestamp

    # Simulate hand detection
    res = DetectionResult(
        timestamp=100,
        type=ResultType.HANDS,
        data={"landmarks": [{}], "handedness": [{}]},
    )
    ws.apply(res)

    assert ws.hands_timestamp > initial


def test_viewport_timestamp_increments():
    ws = WorldState()
    initial = ws.viewport_timestamp

    # Update viewport
    new_vp = ViewportState(x=100, y=200, zoom=2.0)
    ws.update_viewport(new_vp)

    assert ws.viewport_timestamp > initial
    assert ws.viewport == new_vp


def test_tokens_timestamp_idempotency():
    ws = WorldState()
    tokens = [Token(id=1, world_x=10, world_y=20)]
    res = DetectionResult(timestamp=100, type=ResultType.ARUCO, data={"tokens": tokens})
    ws.apply(res)
    ts_after_first = ws.tokens_timestamp

    # Apply same tokens again
    ws.apply(res)
    assert ws.tokens_timestamp == ts_after_first


def test_hands_timestamp_idempotency():
    ws = WorldState()
    # Empty hands
    res = DetectionResult(
        timestamp=100, type=ResultType.HANDS, data={"landmarks": [], "handedness": []}
    )
    ws.apply(res)
    ts_after_first = ws.hands_timestamp

    # Apply empty hands again
    ws.apply(res)
    assert ws.hands_timestamp == ts_after_first


def test_gesture_timestamp_idempotency():
    ws = WorldState()
    res = DetectionResult(
        timestamp=100, type=ResultType.GESTURE, data={"gesture": "OPEN_PALM"}
    )
    ws.apply(res)
    ts_after_first = ws.hands_timestamp

    # Apply same gesture again
    ws.apply(res)
    assert ws.hands_timestamp == ts_after_first


def test_viewport_timestamp_idempotency():
    ws = WorldState()
    vp = ViewportState(x=10, y=20)
    ws.update_viewport(vp)
    ts_after_first = ws.viewport_timestamp

    # Update with same viewport
    ws.update_viewport(vp)
    assert ws.viewport_timestamp == ts_after_first
