import time

from light_map.core.common_types import DetectionResult, ResultType, Token
from light_map.state.world_state import WorldState


def test_token_merging_physical_and_remote():
    """
    Verifies that tokens from physical and remote sources are merged correctly,
    with physical tokens winning on ID conflicts.
    """
    state = WorldState()

    # 1. Inject remote tokens
    remote_token_1 = Token(id=1, world_x=100.0, world_y=100.0, name="Remote 1")
    remote_token_2 = Token(id=2, world_x=200.0, world_y=200.0, name="Remote 2")

    res_remote = DetectionResult(
        timestamp=time.monotonic_ns(),
        type=ResultType.ARUCO,
        data={"tokens": [remote_token_1, remote_token_2]},
    )
    res_remote.metadata["source"] = "remote"

    state.apply(res_remote)

    assert len(state.tokens) == 2
    assert any(t.id == 1 and t.name == "Remote 1" for t in state.tokens)
    assert any(t.id == 2 and t.name == "Remote 2" for t in state.tokens)

    # 2. Inject physical tokens (one new, one conflicting)
    physical_token_2 = Token(id=2, world_x=250.0, world_y=250.0, name="Physical 2")
    physical_token_3 = Token(id=3, world_x=300.0, world_y=300.0, name="Physical 3")

    res_physical = DetectionResult(
        timestamp=time.monotonic_ns(),
        type=ResultType.ARUCO,
        data={"tokens": [physical_token_2, physical_token_3]},
    )
    res_physical.metadata["source"] = "physical"

    state.apply(res_physical)

    # Total should be 3: ID 1 (remote), ID 2 (physical wins), ID 3 (physical)
    assert len(state.tokens) == 3
    token_ids = [t.id for t in state.tokens]
    assert 1 in token_ids
    assert 2 in token_ids
    assert 3 in token_ids

    # Verify ID 2 is physical version
    t2 = next(t for t in state.tokens if t.id == 2)
    assert t2.name == "Physical 2"
    assert t2.world_x == 250.0

    # 3. Update remote tokens (remove 1, add 4)
    remote_token_4 = Token(id=4, world_x=400.0, world_y=400.0, name="Remote 4")
    res_remote_2 = DetectionResult(
        timestamp=time.monotonic_ns(),
        type=ResultType.ARUCO,
        data={
            "tokens": [remote_token_4, remote_token_2]
        },  # remote thinks 2 is still at 200
    )
    res_remote_2.metadata["source"] = "remote"

    state.apply(res_remote_2)

    # Total should be 3: ID 2 (physical wins), ID 3 (physical), ID 4 (remote)
    # ID 1 was removed from remote source.
    assert len(state.tokens) == 3
    token_ids = [t.id for t in state.tokens]
    assert 1 not in token_ids
    assert 2 in token_ids
    assert 3 in token_ids
    assert 4 in token_ids

    # ID 2 should STILL be physical version
    t2 = next(t for t in state.tokens if t.id == 2)
    assert t2.name == "Physical 2"

    # 4. Clear physical tokens
    res_physical_empty = DetectionResult(
        timestamp=time.monotonic_ns(),
        type=ResultType.ARUCO,
        data={"tokens": []},
    )
    res_physical_empty.metadata["source"] = "physical"

    state.apply(res_physical_empty)

    # Now only remote tokens should remain (2 and 4)
    # Note: remote thought 2 was at 200, so it should be back at 200
    assert len(state.tokens) == 2
    token_ids = [t.id for t in state.tokens]
    assert 2 in token_ids
    assert 4 in token_ids
    assert 3 not in token_ids

    t2 = next(t for t in state.tokens if t.id == 2)
    assert t2.name == "Remote 2"
    assert t2.world_x == 200.0
