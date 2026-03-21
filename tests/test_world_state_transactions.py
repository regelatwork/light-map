import time
from light_map.core.world_state import WorldState
from light_map.core.versioned_atom import VersionedAtom

def test_world_state_transaction_batches_timestamps():
    state = WorldState()
    # Mocking atoms for the test since they aren't in WorldState yet
    state.atom1 = VersionedAtom(1, "atom1")
    state.atom2 = VersionedAtom(2, "atom2")
    
    with state.transaction() as tx:
        tx.update(state.atom1, 10)
        tx.update(state.atom2, 20)
        
    assert state.atom1.value == 10
    assert state.atom2.value == 20
    assert state.atom1.timestamp == state.atom2.timestamp
