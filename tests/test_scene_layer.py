import pytest
from unittest.mock import MagicMock
import numpy as np
from light_map.scene_layer import SceneLayer
from light_map.core.world_state import WorldState


@pytest.fixture
def mock_scene():
    scene = MagicMock()

    # Mock render method to return the buffer it received (or modified)
    def side_effect(buffer):
        buffer[0:10, 0:10] = [255, 0, 0]  # Draw Blue square
        return buffer

    scene.render.side_effect = side_effect
    return scene


def test_scene_layer_render(mock_scene):
    ws = WorldState()
    layer = SceneLayer(ws, mock_scene, width=100, height=100)

    patches = layer.render()
    assert len(patches) == 1
    p = patches[0]

    assert p.width == 100
    assert p.height == 100
    # Check BGRA
    assert np.array_equal(p.data[5, 5], [255, 0, 0, 255])
    assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])


def test_scene_layer_caching(mock_scene):
    ws = WorldState()
    layer = SceneLayer(ws, mock_scene, width=100, height=100)

    # 1. First render
    layer.render()
    assert mock_scene.render.call_count == 1

    # 2. Second render
    layer.render()
    assert mock_scene.render.call_count == 1

    # 3. Change timestamp
    ws.increment_scene_timestamp()
    layer.render()
    assert mock_scene.render.call_count == 2
