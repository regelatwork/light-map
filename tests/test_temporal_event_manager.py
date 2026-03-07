import time
from light_map.core.temporal_event_manager import TemporalEventManager


def test_schedule_and_check():
    manager = TemporalEventManager()

    # Store a mutable to check side-effect
    state = {"count": 0}

    def increment():
        state["count"] += 1

    # Schedule for 0.1s in the future
    manager.schedule(0.1, increment)

    # Immediately check - should not run
    manager.check()
    assert state["count"] == 0

    # Wait 0.2s
    time.sleep(0.2)
    manager.check()
    assert state["count"] == 1

    # Check again - should not run twice
    manager.check()
    assert state["count"] == 1


def test_multiple_events_order():
    manager = TemporalEventManager()
    events = []

    manager.schedule(0.2, lambda: events.append("late"))
    manager.schedule(0.1, lambda: events.append("early"))

    time.sleep(0.15)
    manager.check()
    assert events == ["early"]

    time.sleep(0.1)
    manager.check()
    assert events == ["early", "late"]


def test_cancel_event():
    manager = TemporalEventManager()
    state = {"run": False}

    def run():
        state["run"] = True

    manager.schedule(0.1, run, key="test_event")
    manager.cancel("test_event")

    time.sleep(0.2)
    manager.check()
    assert state["run"] is False


def test_supersede_event():
    manager = TemporalEventManager()
    results = []

    manager.schedule(0.1, lambda: results.append("first"), key="exclusive")
    manager.schedule(0.2, lambda: results.append("second"), key="exclusive")

    time.sleep(0.15)
    manager.check()
    # First should have been superseded and not run
    assert results == []

    time.sleep(0.1)
    manager.check()
    assert results == ["second"]
