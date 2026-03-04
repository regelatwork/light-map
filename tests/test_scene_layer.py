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
        buffer[0:10, 0:10] = [255, 0, 0]  # Blue square
        buffer[10:, 10:] = [0, 0, 0]  # Explicit black
        return buffer

    scene.render.side_effect = side_effect
    return scene


def test_scene_layer_render(mock_scene):
    ws = WorldState()
    # Reset mock_scene attributes
    mock_scene.blocking = False
    layer = SceneLayer(ws, mock_scene, width=100, height=100, is_static=False)

    # Mock side effect to have a 'visible' pixel and an 'invisible' pixel
    def side_effect(buffer):
        buffer[5, 5] = [255, 0, 0]  # Blue (visible)
        # Pixel at 20,20 remains [0,0,0] (invisible)
        return buffer

    mock_scene.render.side_effect = side_effect

    patches = layer.render()
    assert len(patches) == 1
    p = patches[0]

    assert p.width == 100
    assert p.height == 100
    # Check BGRA
    assert np.array_equal(p.data[5, 5], [255, 0, 0, 255])  # Opaque
    assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])  # Transparent


def test_scene_layer_blocking(mock_scene):
    ws = WorldState()
    # Mock a scene that is blocking
    mock_scene.blocking = True
    layer = SceneLayer(ws, mock_scene, width=100, height=100, is_static=False)

    def side_effect(buffer):
        buffer[5, 5] = [255, 0, 0]
        return buffer

    mock_scene.render.side_effect = side_effect

    patches = layer.render()
    p = patches[0]
    # In blocking mode, everything is opaque including black background
    assert np.array_equal(p.data[20, 20], [0, 0, 0, 255])


def test_scene_layer_caching(mock_scene):
    ws = WorldState()
    layer = SceneLayer(ws, mock_scene, width=100, height=100, is_static=False)

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
