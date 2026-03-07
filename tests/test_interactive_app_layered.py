import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp
from light_map.common_types import AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 100
    config.height = 100
    config.map_search_patterns = []
    config.storage_manager = None
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.enable_hand_masking = False
    config.hand_mask_padding = 0
    config.camera_resolution = (100, 100)
    config.projector_matrix_resolution = (100, 100)
    config.projector_ppi = 96.0
    return config


def test_interactive_app_layered_init(mock_config, monkeypatch):
    # Mock _load_camera_calibration to avoid file system calls
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)

    assert hasattr(app, "layer_stack")
    assert (
        len(app.layer_stack) == 11
    )  # Map, Door, FoW, Visibility, Scene, Hand, Menu, Token, Notif, Debug, Cursor
    assert app.renderer.output_buffer.shape == (100, 100, 3)


def test_interactive_app_process_state_layered(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state
    ws.last_frame_timestamp = 100

    # We need to mock the current scene's render method to avoid errors
    app.current_scene = MagicMock()
    app.current_scene.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    app.current_scene.update.return_value = None

    frame, messages = app.process_state(ws, [])

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (100, 100, 3)
    # The renderer should have been called
    assert np.all(frame == 0)  # Base black frame


def test_interactive_app_process_state_skips_render_when_not_dirty(
    mock_config, monkeypatch
):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state

    # 1. Initial render (everything is dirty)
    app.current_scene = MagicMock()
    app.current_scene.is_dirty = True
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    frame1, _ = app.process_state(ws, [])
    assert frame1 is not None

    # 2. Subsequent render with no changes should return None
    # We must ensure no pulsing tokens are present to allow skip
    ws.tokens = []

    # We must ensure the scene is clean
    app.current_scene.is_dirty = False

    # Also need to mock get_active_layers to return same stack
    app.current_scene.get_active_layers.return_value = app.layer_stack

    frame2, _ = app.process_state(ws, [])
    assert frame2 is None
