import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.map_layer import MapLayer
from light_map.core.world_state import WorldState


@pytest.fixture
def mock_map_system():
    ms = MagicMock()
    ms.is_map_loaded.return_value = True
    ms.get_render_params.return_value = {
        "scale_factor": 1.0,
        "offset_x": 0,
        "offset_y": 0,
        "rotation": 0,
    }
    ms.svg_loader = MagicMock()
    # Return a 100x100 BGR image
    ms.svg_loader.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    return ms


def test_map_layer_render_basic(mock_map_system):
    ws = WorldState()
    layer = MapLayer(mock_map_system, width=100, height=100)

    patches = layer.render(ws)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.width == 100
    assert patch.height == 100
    assert patch.data.shape == (100, 100, 4)  # Should be BGRA
    assert mock_map_system.svg_loader.render.call_count == 1


def test_map_layer_caching(mock_map_system):
    ws = WorldState()
    layer = MapLayer(mock_map_system, width=100, height=100)

    # First render
    layer.render(ws)
    assert mock_map_system.svg_loader.render.call_count == 1

    # Second render with same timestamps - should use cache
    layer.render(ws)
    assert mock_map_system.svg_loader.render.call_count == 1

    # Third render after incrementing map_timestamp
    ws.increment_map_timestamp()
    layer.render(ws)
    assert mock_map_system.svg_loader.render.call_count == 2


def test_map_layer_not_loaded(mock_map_system):
    mock_map_system.is_map_loaded.return_value = False
    ws = WorldState()
    layer = MapLayer(mock_map_system, width=100, height=100)

    patches = layer.render(ws)
    assert len(patches) == 0
