import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.scene_layer import SceneLayer
from light_map.core.world_state import WorldState


@pytest.fixture
def mock_scene():
    scene = MagicMock()

    # Define render to draw a specific pixel so we can check it
    def render_impl(frame):
        frame[10, 10] = [123, 123, 123]  # BGR
        return frame

    scene.render.side_effect = render_impl
    return scene


def test_scene_layer_render(mock_scene):
    ws = WorldState()
    layer = SceneLayer(mock_scene, width=100, height=100)

    patches = layer.render(ws)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.width == 100
    assert patch.height == 100
    assert patch.data.shape == (100, 100, 4)
    # Check if scene drew onto it
    assert np.array_equal(patch.data[10, 10, :3], [123, 123, 123])
    # Alpha should be 255 where drawn
    assert patch.data[10, 10, 3] == 255
    # Alpha should be 0 where NOT drawn
    assert patch.data[0, 0, 3] == 0


def test_scene_layer_caching(mock_scene):
    ws = WorldState()
    layer = SceneLayer(mock_scene, width=100, height=100)

    # 1. First render
    layer.render(ws)
    assert mock_scene.render.call_count == 1

    # 2. Second render (no change) - should use cache
    layer.render(ws)
    assert mock_scene.render.call_count == 1

    # 3. Third render (timestamp changed) - re-renders
    ws.increment_scene_timestamp()
    layer.render(ws)
    assert mock_scene.render.call_count == 2
