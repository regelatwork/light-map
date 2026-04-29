from light_map.core.common_types import (
    DetectionResult,
    ResultType,
    Token,
    ViewportState,
)
from light_map.state.world_state import WorldState


def test_world_state_timestamps_init():
    ws = WorldState()
    assert ws.map_version > 0
    assert ws.menu_version > 0
    assert ws.tokens_version > 0
    assert ws.hands_version > 0
    assert ws.notifications_version > 0
    assert ws.viewport_version > 0


def test_tokens_version_increments():
    ws = WorldState()
    initial = ws.tokens_version

    # Simulate a change in tokens
    tokens = [Token(id=1, world_x=10, world_y=20)]
    res = DetectionResult(timestamp=100, type=ResultType.ARUCO, data={"tokens": tokens})
    ws.apply(res)

    assert ws.tokens_version > initial
    assert ws.tokens == tokens


def test_hands_version_increments():
    ws = WorldState()
    initial = ws.hands_version

    # Simulate hand detection
    res = DetectionResult(
        timestamp=100,
        type=ResultType.HANDS,
        data={"landmarks": [{}], "handedness": [{}]},
    )
    ws.apply(res)

    assert ws.hands_version > initial


def test_viewport_version_increments():
    ws = WorldState()
    initial = ws.viewport_version

    # Update viewport
    new_vp = ViewportState(x=100, y=200, zoom=2.0)
    ws.update_viewport(new_vp)

    assert ws.viewport_version > initial
    assert ws.viewport == new_vp


def test_tokens_version_idempotency():
    ws = WorldState()
    tokens = [Token(id=1, world_x=10, world_y=20)]
    res = DetectionResult(timestamp=100, type=ResultType.ARUCO, data={"tokens": tokens})
    ws.apply(res)
    ts_after_first = ws.tokens_version

    # Apply same tokens again
    ws.apply(res)
    assert ws.tokens_version == ts_after_first


def test_hands_version_idempotency():
    ws = WorldState()
    # Empty hands
    res = DetectionResult(
        timestamp=100, type=ResultType.HANDS, data={"landmarks": [], "handedness": []}
    )
    ws.apply(res)
    ts_after_first = ws.hands_version

    # Apply empty hands again
    ws.apply(res)
    assert ws.hands_version == ts_after_first


def test_gesture_timestamp_idempotency():
    ws = WorldState()
    res = DetectionResult(
        timestamp=100, type=ResultType.GESTURE, data={"gesture": "OPEN_PALM"}
    )
    ws.apply(res)
    ts_after_first = ws.hands_version

    # Apply same gesture again
    ws.apply(res)
    assert ws.hands_version == ts_after_first


def test_viewport_version_idempotency():
    ws = WorldState()
    vp = ViewportState(x=10, y=20)
    ws.update_viewport(vp)
    ts_after_first = ws.viewport_version

    # Update with same viewport
    ws.update_viewport(vp)
    assert ws.viewport_version == ts_after_first
