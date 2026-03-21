from light_map.core.world_state import WorldState
from light_map.common_types import Token

def test_tokens_use_optimized_equality():
    state = WorldState()
    t1 = Token(id=1, world_x=10.0, world_y=10.0)
    state.tokens = [t1]
    ts1 = state.tokens_timestamp
    
    # Update with semantically identical token (tiny jitter)
    t1_jitter = Token(id=1, world_x=10.1, world_y=10.1)
    state.tokens = [t1_jitter]
    
    assert state.tokens_timestamp == ts1 # Should NOT change

def test_tokens_atomic_updates():
    state = WorldState()
    t1 = Token(id=1, world_x=10.0, world_y=10.0)
    ts0 = state.tokens_timestamp
    state.tokens = [t1]
    assert state.tokens_timestamp > ts0 # Currently FAILS because tokens is not yet an atom/property
