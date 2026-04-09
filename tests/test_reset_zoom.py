import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp
from light_map.core.common_types import AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    config.map_search_patterns = []
    config.storage_manager = None
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (1920, 1080)
    config.projector_matrix_resolution = (1920, 1080)
    config.projector_ppi = 96.0
    return config


def test_reset_zoom_action(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)

    # Mock map_system.reset_zoom_to_base
    app.map_system.reset_zoom_to_base = MagicMock()

    # Mock notification manager
    app.notifications.add_notification = MagicMock()

    # Create a WorldState with a pending RESET_ZOOM action
    ws = app.state
    ws.pending_actions.append({"action": "RESET_ZOOM"})

    # Process state
    app.current_scene = MagicMock()
    app.current_scene.update.return_value = None
    app.current_scene.render.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)

    app.process_state(ws, [])

    # Verify reset_zoom_to_base was called
    app.map_system.reset_zoom_to_base.assert_called_once()

    # Verify notification was added
    app.notifications.add_notification.assert_called_with("Zoom Reset to 1:1")

    # Verify pending_actions was cleared
    assert len(ws.pending_actions) == 0
