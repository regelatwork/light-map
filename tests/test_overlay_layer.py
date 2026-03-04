import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from light_map.overlay_layer import TokenLayer, NotificationLayer, DebugLayer
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


def test_notification_layer_render(mock_app_context):
    ws = WorldState()
    ws.notifications_timestamp = 1

    layer = NotificationLayer(ws, mock_app_context)

    # Mock OverlayRenderer to avoid complex logic
    from light_map.common_types import ImagePatch

    with patch.object(layer.overlay_renderer, "draw_notifications") as mock_draw:
        # Side effect: return a mock patch
        def draw_side_effect():
            data = np.zeros((1080, 1920, 4), dtype=np.uint8)
            data[0:10, 0:10] = [255, 255, 255, 255]
            return [ImagePatch(x=0, y=0, width=1920, height=1080, data=data)]

        mock_draw.side_effect = draw_side_effect

        patches = layer.render()

        assert len(patches) == 1
        p = patches[0]
        assert p.width == 1920
        assert p.height == 1080
        # Check alpha
        assert np.array_equal(p.data[5, 5], [255, 255, 255, 255])
        assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])


def test_token_layer_render(mock_app_context):
    ws = WorldState()
    ws.tokens = [MagicMock()]
    ws.tokens_timestamp = 1

    layer = TokenLayer(ws, mock_app_context)

    with patch.object(layer.overlay_renderer, "draw_ghost_tokens") as mock_draw:
        layer.render()
        assert mock_draw.called


def test_debug_layer_render(mock_app_context):
    ws = WorldState()
    ws.hands_timestamp = 1
    mock_app_context.debug_mode = True

    layer = DebugLayer(ws, mock_app_context)

    with patch.object(layer.overlay_renderer, "draw_debug_overlay") as mock_draw:
        layer.render()
        assert mock_draw.called


def test_token_layer_caching(mock_app_context):
    ws = WorldState()
    ws.tokens = [MagicMock()]
    ws.tokens_timestamp = 1

    layer = TokenLayer(ws, mock_app_context)

    with patch.object(layer.overlay_renderer, "draw_ghost_tokens") as mock_draw:
        mock_draw.side_effect = lambda *args: [MagicMock()]
        p1 = layer.render()
        p2 = layer.render()
        assert p1 is p2

        # Change timestamp
        ws.tokens_timestamp += 1
        p3 = layer.render()
        assert p3 is not p1
