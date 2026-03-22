from light_map.core.world_state import WorldState
from light_map.core.temporal_event_manager import TemporalEventManager


def test_temporal_manager_updates_system_time():
    state = WorldState()
    # Injected into MainLoop/InteractiveApp usually
    tem = TemporalEventManager(time_provider=lambda: 100.0)
    tem.state = state  # Assign state manually for test

    initial_time = state.system_time
    # This should be called in the loop
    tem.advance(1.0)

    assert state.system_time > initial_time
    assert state.system_time_version > 0
