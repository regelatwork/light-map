import time
from unittest.mock import MagicMock
import pytest

from light_map.action_dispatcher import handle_trigger_ping
from light_map.state.world_state import WorldState
from light_map.core.common_types import Action

def test_ping_lifecycle():
    # Setup
    state = WorldState()
    app = MagicMock()
    app.events = MagicMock()
    
    # Store the callback for manual execution
    scheduled_callback = None
    def mock_schedule(delay, callback):
        nonlocal scheduled_callback
        scheduled_callback = callback
    
    app.events.schedule.side_effect = mock_schedule
    
    payload = {"action": Action.TRIGGER_PING, "token_id": "test_token"}
    
    # Execute
    handle_trigger_ping(app, payload, state)
    
    # Verify ping added
    assert "test_token" in state.active_pings
    assert state.active_pings["test_token"] > 0
    app.events.schedule.assert_called_once()
    
    # Verify cleanup callback works
    assert scheduled_callback is not None
    scheduled_callback()
    assert "test_token" not in state.active_pings

def test_multiple_pings():
    state = WorldState()
    app = MagicMock()
    
    handle_trigger_ping(app, {"token_id": "token1"}, state)
    handle_trigger_ping(app, {"token_id": "token2"}, state)
    
    assert "token1" in state.active_pings
    assert "token2" in state.active_pings
    assert len(state.active_pings) == 2
