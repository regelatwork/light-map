import numpy as np

from light_map.core.common_types import MapRenderState
from light_map.state.world_state import WorldState


def test_map_version_data_driven():
    ws = WorldState()
    initial = ws.map_version

    # Update map render state
    ws.map_render_state = MapRenderState(opacity=0.5, quality=50, filepath="test.svg")
    assert ws.map_version > initial
    v1 = ws.map_version

    # Update with same data - version should NOT change
    ws.map_render_state = MapRenderState(opacity=0.5, quality=50, filepath="test.svg")
    assert ws.map_version == v1

    # Update with different data
    ws.map_render_state = MapRenderState(opacity=0.6, quality=50, filepath="test.svg")
    assert ws.map_version > v1


def test_fow_version_data_driven():
    ws = WorldState()
    initial = ws.fow_version

    # Update FOW mask
    mask = np.zeros((100, 100), dtype=np.uint8)
    ws.fow_mask = mask
    assert ws.fow_version > initial
    v1 = ws.fow_version

    # Update with same data (np.array_equal)
    ws.fow_mask = mask.copy()
    assert ws.fow_version == v1

    # Update with different data
    new_mask = mask.copy()
    new_mask[0, 0] = 255
    ws.fow_mask = new_mask
    assert ws.fow_version > v1


def test_visibility_version_data_driven():
    ws = WorldState()
    initial = ws.visibility_version

    # Update visibility mask
    mask = np.zeros((100, 100), dtype=np.uint8)
    ws.visibility_mask = mask
    assert ws.visibility_version > initial
    v1 = ws.visibility_version

    # Update with same data
    ws.visibility_mask = mask.copy()
    assert ws.visibility_version == v1

    # Update with different data
    new_mask = mask.copy()
    new_mask[0, 0] = 255
    ws.visibility_mask = new_mask
    assert ws.visibility_version > v1


def test_version_setters_removed():
    ws = WorldState()
    import pytest

    with pytest.raises(AttributeError):
        ws.map_version = 1
    with pytest.raises(AttributeError):
        ws.fow_version = 1
    with pytest.raises(AttributeError):
        ws.scene_version = 1
    with pytest.raises(AttributeError):
        ws.tokens_version = 1
    with pytest.raises(AttributeError):
        ws.visibility_version = 1
    with pytest.raises(AttributeError):
        ws.notifications_version = 1


def test_to_dict_tactical_type():
    from light_map.core.common_types import CoverResult, Token

    token = Token(id=1, world_x=1.0, world_y=2.0, type="PC")
    ws = WorldState()
    ws.tokens = [token]
    ws.tactical_bonuses = {
        1: CoverResult(
            ac_bonus=10,
            reflex_bonus=5,
            best_apex=(0, 0),
            segments=[],
            npc_pixels=np.array([]),
            total_ratio=0.5,
            wall_ratio=0.3,
            soft_ratio=0.2,
            explanation="Test",
        )
    }

    result = ws.to_dict()
    tactical = result["tactical"]

    assert len(tactical["targets"]) == 1
    assert tactical["targets"][0]["id"] == 1
    assert tactical["targets"][0]["type"] == "PC"
