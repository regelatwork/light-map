import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.overlay_layer import OverlayLayer
from light_map.core.world_state import WorldState
from light_map.core.app_context import AppContext


@pytest.fixture
def mock_app_context():
    context = MagicMock(spec=AppContext)
    context.app_config = MagicMock()
    context.app_config.width = 100
    context.app_config.height = 100
    context.show_tokens = True
    context.debug_mode = False

    # Mock MapConfigManager
    context.map_config_manager = MagicMock()
    context.map_config_manager.get_ppi.return_value = 10
    context.map_config_manager.resolve_token_profile.return_value = MagicMock(
        is_known=True, name="Token", type="PC"
    )

    # Mock MapSystem
    context.map_system = MagicMock()
    context.map_system.ghost_tokens = []
    context.map_system.world_to_screen.return_value = (50, 50)

    # Mock Notifications
    context.notifications = MagicMock()
    context.notifications.get_active_notifications.return_value = []
    context.notifications.has_active.return_value = False

    return context


def test_overlay_layer_render_notifications(mock_app_context):
    ws = WorldState()
    ws.notifications_timestamp = 1

    # Mock NotificationManager having active notifications
    mock_app_context.notifications.get_active_notifications.return_value = ["Test Msg"]
    mock_app_context.notifications.has_active.return_value = True

    layer = OverlayLayer(mock_app_context)
    patches = layer.render(ws)

    assert len(patches) > 0
    assert patches[0].width == 100
    assert patches[0].height == 100
    # Should have some opaque pixels
    assert np.any(patches[0].data[:, :, 3] == 255)


def test_overlay_layer_render_tokens(mock_app_context):
    ws = WorldState()
    ws.tokens = [MagicMock()]
    ws.tokens_timestamp = 1

    # Sync mock_app_context.map_system with state tokens
    mock_app_context.map_system.ghost_tokens = ws.tokens

    layer = OverlayLayer(mock_app_context)
    patches = layer.render(ws)

    assert len(patches) > 0
    assert np.any(patches[0].data[:, :, 3] == 255)


def test_overlay_layer_caching(mock_app_context):
    ws = WorldState()
    ws.notifications_timestamp = 1

    layer = OverlayLayer(mock_app_context)

    # 1. First render
    layer.render(ws)
    assert layer.last_rendered_timestamp == 1

    # 2. Second render (no change)
    layer.render(ws)
    assert layer.last_rendered_timestamp == 1

    # 3. Third render (timestamp changed)
    ws.increment_notifications_timestamp()
    layer.render(ws)
    assert layer.last_rendered_timestamp == 2
