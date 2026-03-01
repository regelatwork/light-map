import time
import pytest
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
    # If we need cancellation (design didn't specify, but good to have)
    pass
