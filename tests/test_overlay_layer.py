from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.core.app_context import AppContext
from light_map.core.common_types import AppConfig
from light_map.rendering.layers.overlay_layer import (
    DebugLayer,
    NotificationLayer,
    TokenLayer,
)
from light_map.state.world_state import WorldState


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
    ws.notifications = ["Test"]

    layer = NotificationLayer(ws, mock_app_context)

    # Mock OverlayRenderer to avoid complex logic
    from light_map.core.common_types import ImagePatch

    with patch.object(layer.overlay_renderer, "draw_notifications") as mock_draw:
        # Side effect: return a mock patch
        def draw_side_effect():
            data = np.zeros((1080, 1920, 4), dtype=np.uint8)
            data[0:10, 0:10] = [255, 255, 255, 255]
            return [ImagePatch(x=0, y=0, width=1920, height=1080, data=data)]

        mock_draw.side_effect = draw_side_effect

        patches = layer.render()[0]

        assert len(patches) == 1
        p = patches[0]
        assert p.width == 1920
        assert p.height == 1080
        # Check alpha
        assert np.array_equal(p.data[5, 5], [255, 255, 255, 255])
        assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])


def test_token_layer_render(mock_app_context):
    from light_map.core.common_types import Token

    ws = WorldState()
    ws.tokens = [Token(id=1, world_x=10, world_y=10)]

    layer = TokenLayer(ws, mock_app_context, time_provider=lambda: 0.0)

    with patch.object(layer.overlay_renderer, "draw_ghost_tokens") as mock_draw:
        layer.render()[0]
        assert mock_draw.called


def test_debug_layer_render(mock_app_context):
    from light_map.core.common_types import GestureType
    from light_map.core.scene import HandInput

    ws = WorldState()
    # Trigger hands_version change by setting an input
    ws.inputs = [
        HandInput(
            gesture=GestureType.POINTING,
            proj_pos=(100, 100),
            unit_direction=(1, 0),
            raw_landmarks=None,
        )
    ]
    mock_app_context.debug_mode = True

    layer = DebugLayer(ws, mock_app_context)

    with patch.object(layer.overlay_renderer, "draw_debug_overlay") as mock_draw:
        layer.render()[0]
        assert mock_draw.called

    def test_token_layer_caching(mock_app_context):
        from light_map.core.common_types import Token

        ws = WorldState()
        ws.tokens = [Token(id=1, world_x=10, world_y=10)]

        layer = TokenLayer(ws, mock_app_context, time_provider=lambda: 0.0)

        with patch.object(layer.overlay_renderer, "draw_ghost_tokens") as mock_draw:
            # Return a DIFFERENT list with DIFFERENT contents to ensure 'is not' works
            p1_data = [MagicMock(name="p1")]
            mock_draw.return_value = p1_data

            p1, v1 = layer.render()
            p2, v2 = layer.render()
            assert p1 is p2
            assert v1 == v2

            # Change tokens to trigger version increment
            ws.tokens = [Token(id=1, world_x=11, world_y=11)]

            p3_data = [MagicMock(name="p3")]
            mock_draw.return_value = p3_data

        p3, v3 = layer.render()
        assert v3 > v1
        assert p3 is not p1
