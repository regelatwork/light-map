import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from light_map.overlay_layer import OverlayLayer
from light_map.core.world_state import WorldState
from light_map.core.app_context import AppContext
from light_map.common_types import AppConfig


@pytest.fixture
def mock_app_context():
    # Properly mock AppContext and its nested attributes
    config = MagicMock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    
    ctx = MagicMock(spec=AppContext)
    ctx.app_config = config
    ctx.debug_mode = False
    ctx.show_tokens = True
    
    # Nested attributes that OverlayRenderer uses
    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.get_ppi.return_value = 100.0
    ctx.notifications = MagicMock()
    ctx.notifications.get_active_notifications.return_value = []
    
    return ctx


def test_overlay_layer_render_notifications(mock_app_context):
    ws = WorldState()
    ws.notifications_timestamp = 1

    layer = OverlayLayer(ws, mock_app_context)

    # Mock OverlayRenderer to avoid complex logic
    with patch.object(layer.overlay_renderer, "draw_notifications") as mock_draw:
        # Side effect: draw something on buffer
        def draw_side_effect(buffer):
            buffer[0:10, 0:10] = [255, 255, 255]
        mock_draw.side_effect = draw_side_effect
        
        # Also need to mock other methods called in _generate_patches
        with patch.object(layer.overlay_renderer, "draw_ghost_tokens"):
            patches = layer.render()

            assert len(patches) == 1
            p = patches[0]
            assert p.width == 1920
            assert p.height == 1080
            # Check alpha
            assert np.array_equal(p.data[5, 5], [255, 255, 255, 255])
            assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])


def test_overlay_layer_render_tokens(mock_app_context):
    ws = WorldState()
    ws.tokens = [MagicMock()]
    ws.tokens_timestamp = 1

    layer = OverlayLayer(ws, mock_app_context)
    
    with patch.object(layer.overlay_renderer, "draw_ghost_tokens") as mock_draw:
        with patch.object(layer.overlay_renderer, "draw_notifications"):
            layer.render()
            assert mock_draw.called


def test_overlay_layer_caching(mock_app_context):
    ws = WorldState()
    ws.notifications_timestamp = 1

    layer = OverlayLayer(ws, mock_app_context)

    with patch.object(layer.overlay_renderer, "draw_notifications"):
        with patch.object(layer.overlay_renderer, "draw_ghost_tokens"):
            p1 = layer.render()
            p2 = layer.render()
            assert p1 is p2

            # Change timestamp
            ws.increment_notifications_timestamp()
            p3 = layer.render()
            assert p3 is not p1
