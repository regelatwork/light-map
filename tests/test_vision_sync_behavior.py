import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp
from light_map.core.common_types import AppConfig, Token


@pytest.fixture
def mock_app():
    config = AppConfig(width=100, height=100, projector_matrix=np.eye(3))
    # Mock systems that InteractiveApp initializes
    with (
        patch("light_map.interactive_app.Renderer"),
        patch("light_map.interactive_app.MapSystem"),
        patch("light_map.interactive_app.MapConfigManager"),
        patch("light_map.interactive_app.TrackingCoordinator"),
        patch(
            "light_map.interactive_app.InteractiveApp._load_camera_calibration"
        ) as mock_cal,
        patch("light_map.interactive_app.VisibilityEngine") as mock_ve_class,
    ):
        mock_cal.return_value = (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3))

        # Setup mock visibility engine
        mock_ve = mock_ve_class.return_value
        # Return a simple 10x10 mask where (0,0) is visible
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[0, 0] = 255
        mock_ve.get_token_vision_mask.return_value = mask
        mock_ve.get_aggregate_vision_mask.return_value = mask

        app = InteractiveApp(config)
        # Manually inject a loaded map state
        app.map_system.is_map_loaded.return_value = True
        app.map_system.world_to_screen.return_value = (0.0, 0.0)
        app.fow_manager = MagicMock()
        app.fow_manager.width = 10
        app.fow_manager.height = 10
        app.fow_manager.visible_mask = np.zeros((10, 10), dtype=np.uint8)

        return app


def test_vision_frozen_until_sync(mock_app):
    """Verify that moving a token does NOT update the visible mask until Sync Vision is called."""
    app = mock_app
    app.current_map_path = "/tmp/test_map.svg"
    state = app.state

    # 1. Add a PC token
    pc_token = Token(id=1, world_x=5, world_y=5)
    state.tokens = [pc_token]
    # Mock profile resolution to be PC
    app.map_config.resolve_token_profile.return_value.type = "PC"
    app.map_config.resolve_token_profile.return_value.size = 1

    # 2. Run a processing cycle (simulates token movement detection)
    app.process_state(state, [])

    # 3. Check that the fow_manager's visible_mask is still empty (NOT updated)
    assert np.all(app.fow_manager.visible_mask == 0)

    # 4. Trigger Sync Vision (Now calculates vision on-demand)
    app._handle_payloads({"action": "SYNC_VISION"}, state)

    # 5. Check that the fow_manager's visible_mask is NOW updated
    app.fow_manager.set_visible_mask.assert_called_once()
    # Check that world state visibility mask is updated
    assert state.visibility_mask is not None
    assert state.visibility_mask[0, 0] == 255
