from light_map.core.world_state import WorldState
from light_map.common_types import DetectionResult, ResultType, Token, ViewportState


def test_world_state_timestamps_init():
    ws = WorldState()
    assert ws.map_timestamp == 0
    assert ws.menu_timestamp == 0
    assert ws.tokens_timestamp == 0
    assert ws.hands_timestamp == 0
    assert ws.notifications_timestamp == 0
    assert ws.viewport_timestamp == 0


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


def test_map_and_menu_timestamps():
    ws = WorldState()

    # Manual increments for now as these are often triggered by app logic
    ws.increment_map_timestamp()
    assert ws.map_timestamp == 1

    ws.increment_menu_timestamp()
    assert ws.menu_timestamp == 1

    ws.increment_notifications_timestamp()
    assert ws.notifications_timestamp == 1
