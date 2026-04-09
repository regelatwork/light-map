import time
import pytest
from light_map.state.temporal_event_manager import TemporalEventManager
from light_map.input.dwell_tracker import DwellTracker


def test_temporal_event_manager_remaining_time():
    events = TemporalEventManager()
    key = "test_event"

    # Schedule event for 2 seconds in the future
    events.schedule(2.0, lambda: None, key=key)

    # Check remaining time (should be close to 2.0)
    rem = events.get_remaining_time(key)
    assert 1.9 <= rem <= 2.0

    # Wait a bit
    time.sleep(0.5)
    rem2 = events.get_remaining_time(key)
    assert 1.4 <= rem2 <= 1.5

    # Cancel event
    events.cancel(key)
    assert events.get_remaining_time(key) == 0.0


def test_dwell_tracker_accumulated_time_with_events():
    events = TemporalEventManager()
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0, events=events)

    # Initially 0
    assert tracker.accumulated_time == pytest.approx(0.0, abs=1e-5)

    # Update to start dwelling
    tracker.update((100, 100), 0.1)

    # Progress should be tracked
    time.sleep(0.5)
    acc = tracker.accumulated_time
    assert 0.4 <= acc <= 0.6

    # Move outside radius
    tracker.update((200, 200), 0.1)
    assert tracker.accumulated_time == pytest.approx(0.0, abs=1e-4)

    # Start dwelling again
    tracker.update((200, 200), 0.1)
    time.sleep(0.5)
    assert 0.4 <= tracker.accumulated_time <= 0.6

    # Trigger event
    time.sleep(1.6)
    events.check()
    assert tracker.is_triggered is True
    assert tracker.accumulated_time == 2.0


def test_dwell_tracker_accumulated_time_no_events():
    events = TemporalEventManager()
    t = 0.0
    events.time_provider = lambda: t
    tracker = DwellTracker(radius_pixels=10, dwell_time_threshold=2.0, events=events)

    # Initially 0
    assert tracker.accumulated_time == 0.0

    # Update
    tracker.update((100, 100), 0.5)
    assert tracker.accumulated_time == 0.0

    t = 0.5
    assert tracker.accumulated_time == 0.5

    t = 1.5
    assert tracker.accumulated_time == 1.5

    t = 2.0
    events.check()
    tracker.update((101, 101), 0.5)
    assert tracker.accumulated_time == 2.0
    assert tracker.is_triggered is True
