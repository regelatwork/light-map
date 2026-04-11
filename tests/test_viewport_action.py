import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp, AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 1000
    config.height = 750
    config.map_search_patterns = []
    config.storage_manager = None
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (1280, 720)
    config.projector_matrix_resolution = (1000, 750)
    config.projector_ppi = 96.0
    return config


def test_handle_set_viewport_action(mock_config, monkeypatch):
    # Mock _load_camera_calibration to avoid file system calls
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state

    # 1. Setup mock scene and state
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = []
    app.current_scene.render.return_value = (np.zeros((750, 1000, 3), dtype=np.uint8), 1)

    # Initial state
    assert app.map_system.state.x == 0.0
    assert app.map_system.state.y == 0.0
    assert app.map_system.state.zoom == 1.0

    # 2. Inject SET_VIEWPORT action with new naming (x, y)
    viewport_data = {
        "action": "SET_VIEWPORT",
        "x": 500.0,
        "y": 375.0,
        "zoom": 2.0,
        "rotation": 90.0,
    }
    ws.pending_actions.append(viewport_data)

    app.process_state(ws, [])

    # Verify state updated correctly
    assert app.map_system.state.x == 500.0
    assert app.map_system.state.y == 375.0
    assert app.map_system.state.zoom == 2.0
    assert app.map_system.state.rotation == 90.0
    assert len(ws.pending_actions) == 0

def test_handle_set_viewport_action_partial(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state

    app.current_scene = MagicMock()
    app.current_scene.render.return_value = (np.zeros((750, 1000, 3), dtype=np.uint8), 1)

    # Inject only ZOOM
    ws.pending_actions.append({
        "action": "SET_VIEWPORT",
        "zoom": 1.5,
    })

    app.process_state(ws, [])

    assert app.map_system.state.zoom == 1.5
    assert app.map_system.state.x == 0.0 # Unchanged
    assert app.map_system.state.y == 0.0 # Unchanged
