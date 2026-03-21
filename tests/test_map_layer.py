import pytest
from unittest.mock import MagicMock
import numpy as np
from light_map.map_layer import MapLayer
from light_map.core.world_state import WorldState


@pytest.fixture
def mock_map_system():
    ms = MagicMock()
    ms.is_map_loaded.return_value = True
    ms.get_render_params.return_value = {"x": 0, "y": 0, "zoom": 1.0}

    # Mock SVG Loader
    loader = MagicMock()
    # Returns a 100x100 BGR Green image
    green_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    green_bgr[:, :, 1] = 255
    loader.render.return_value = green_bgr
    ms.svg_loader = loader

    return ms


def test_map_layer_render_basic(mock_map_system):
    ws = WorldState()
    layer = MapLayer(ws, mock_map_system, width=100, height=100)

    patches = layer.render()[0]
    assert len(patches) == 1
    patch = patches[0]

    assert patch.x == 0
    assert patch.y == 0
    assert patch.width == 100
    assert patch.height == 100
    # Should be BGRA
    assert patch.data.shape == (100, 100, 4)
    assert np.array_equal(patch.data[50, 50, :3], [0, 255, 0])
    assert patch.data[50, 50, 3] == 255


def test_map_layer_caching(mock_map_system):
    ws = WorldState()
    layer = MapLayer(ws, mock_map_system, width=100, height=100)

    # 1. Initial render
    p1, v1 = layer.render()
    assert mock_map_system.svg_loader.render.call_count == 1

    # 2. Render again with same params - should use cache
    p2, v2 = layer.render()
    assert mock_map_system.svg_loader.render.call_count == 1
    assert p1 is p2
    assert v1 == v2

    # 3. Change params - should trigger re-render
    # We must ensure get_current_version() also increases if we want Layer to re-call _generate_patches
    # MapLayer.get_current_version checks map_timestamp, viewport_timestamp and self._version
    ws.map_version += 1

    mock_map_system.get_render_params.return_value = {"x": 10, "y": 0, "zoom": 1.0}
    p3, v3 = layer.render()
    assert mock_map_system.svg_loader.render.call_count == 2
    assert v3 > v1
    assert p3 is not p1


def test_map_layer_not_loaded(mock_map_system):
    mock_map_system.is_map_loaded.return_value = False
    ws = WorldState()
    layer = MapLayer(ws, mock_map_system, width=100, height=100)

    patches = layer.render()[0]
    assert len(patches) == 0
