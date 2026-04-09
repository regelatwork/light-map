from light_map.state.world_state import WorldState
from light_map.core.common_types import MapRenderState
import numpy as np


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
