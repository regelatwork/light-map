from light_map.vision.processing.token_merge_manager import TokenMergeManager
from light_map.core.common_types import (
    DetectionResult,
    ResultType,
    Token,
    TokenMergePolicy,
)


def test_token_merge_manager_policies():
    manager = TokenMergeManager(policy=TokenMergePolicy.PHYSICAL_PRIORITY)

    remote_t1 = Token(id=1, world_x=10.0, world_y=10.0, name="Remote 1")
    physical_t1 = Token(id=1, world_x=20.0, world_y=20.0, name="Physical 1")
    physical_t2 = Token(id=2, world_x=30.0, world_y=30.0, name="Physical 2")

    res_remote = DetectionResult(
        timestamp=0,
        type=ResultType.ARUCO,
        data={"tokens": [remote_t1]},
        metadata={"source": "remote"},
    )
    res_physical = DetectionResult(
        timestamp=0,
        type=ResultType.ARUCO,
        data={"tokens": [physical_t1, physical_t2]},
        metadata={"source": "physical"},
    )

    manager.update_source(res_remote)
    manager.update_source(res_physical)

    # Physical Priority (Default)
    merged = manager.get_merged_tokens()
    assert len(merged) == 2
    t1 = next(t for t in merged if t.id == 1)
    assert t1.name == "Physical 1"

    # Remote Priority
    manager.set_policy(TokenMergePolicy.REMOTE_PRIORITY)
    merged = manager.get_merged_tokens()
    assert len(merged) == 2
    t1 = next(t for t in merged if t.id == 1)
    assert t1.name == "Remote 1"

    # Physical Only
    manager.set_policy(TokenMergePolicy.PHYSICAL_ONLY)
    merged = manager.get_merged_tokens()
    assert len(merged) == 2
    assert all(t.name.startswith("Physical") for t in merged)

    # Remote Only
    manager.set_policy(TokenMergePolicy.REMOTE_ONLY)
    merged = manager.get_merged_tokens()
    assert len(merged) == 1
    assert merged[0].name == "Remote 1"
