import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp
from light_map.core.common_types import AppConfig


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
    stack = app.layer_stack
    assert (
        len(stack) == 9
    )  # BackgroundComposite, Hand, Token, Menu, Notif, Debug, SelectionProgress, Cursor, ArucoMask

    # Verify background_composite is the first layer
    from light_map.core.common_types import CompositeLayer

    assert isinstance(stack[0], CompositeLayer)
    assert stack[0] == app.layer_manager.background_composite

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
    app.current_scene.render.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), 1)
    app.current_scene.update.return_value = None

    frame, messages = app.process_state(ws, [])

    assert isinstance(frame, np.ndarray)
    assert frame.shape == (100, 100, 3)
    # The renderer should have been called
    assert np.all(frame == 0)  # Base black frame


def test_interactive_app_process_state_skips_render_when_not_stale(
    mock_config, monkeypatch
):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state
    ws.effective_show_tokens = False

    # Ensure map system is in sync with state viewport initially
    ws.viewport = app.map_system.state.to_viewport()

    # 1. Initial render (everything is stale/initial)
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.is_dynamic = False
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), 1)

    # Sync state name to avoid update between calls
    ws.current_scene_name = app.current_scene.__class__.__name__
    # Sync show_tokens to avoid update from context
    app.app_context.show_tokens = False

    frame1, _ = app.process_state(ws, [])
    assert frame1 is not None

    # 2. Subsequent render with no changes should return None
    # We must ensure no pulsing tokens are present to allow skip
    ws.tokens = []

    # Ensure last_scene_version is synced
    app.last_scene_version = app.current_scene.version

    # Also need to mock get_active_layers to return same stack
    app.current_scene.get_active_layers.return_value = app.layer_stack

    frame2, _ = app.process_state(ws, [])
    assert frame2 is None


def test_interactive_app_process_state_actions(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state

    # 1. Setup mock scene
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.side_effect = lambda f: (
        f,
        1,
    )  # Return the buffer passed in

    # 2. Inject ZOOM action
    initial_zoom = app.map_system.state.zoom
    ws.pending_actions.append({"action": "ZOOM", "delta": 0.5})

    app.process_state(ws, [])

    # Expected: zoom * (1.0 + 0.5)
    assert app.map_system.state.zoom == initial_zoom * 1.5
    assert len(ws.pending_actions) == 0

    # 3. Inject Generic Action (SYNC_VISION)
    app._sync_vision = MagicMock()
    ws.pending_actions.append({"action": "SYNC_VISION"})

    app.process_state(ws, [])

    app._sync_vision.assert_called_once_with(ws)
    assert len(ws.pending_actions) == 0

    # 4. Inject TOGGLE_DOOR action with door_id
    from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType

    door = VisibilityBlocker(
        points=[(0, 0), (10, 10)],
        type=VisibilityType.DOOR,
        layer_name="doors",
        id="door123",
        is_open=False,
    )
    app.visibility_engine.blockers = [door]
    app.fow_manager = MagicMock()
    app.fow_manager.width = 100
    app.fow_manager.height = 100


def test_interactive_app_update_token_action(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    ws = app.state

    # 1. Setup mock scene
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.side_effect = lambda f: (f, 1)

    # 2. Inject UPDATE_TOKEN action (Profile Only)
    token_id = 999
    update_data = {
        "action": "UPDATE_TOKEN",
        "id": token_id,
        "name": "Super Hero",
        "color": "#00ff00",
        "type": "PC",
        "profile": "hero_profile",
    }
    ws.pending_actions.append(update_data)

    app.process_state(ws, [])

    # Verify Profile was updated and custom dims cleared
    aruco_def = app.map_config.data.global_settings.aruco_defaults.get(token_id)
    assert aruco_def is not None
    assert aruco_def.profile == "hero_profile"
    assert aruco_def.size is None

    # 3. Inject UPDATE_TOKEN action (Custom Dims Only)
    update_data_custom = {
        "action": "UPDATE_TOKEN",
        "id": token_id,
        "size": 3,
        "height_mm": 50.0,
    }
    ws.pending_actions.append(update_data_custom)
    app.process_state(ws, [])

    # Verify custom dims were updated and profile cleared
    aruco_def = app.map_config.data.global_settings.aruco_defaults.get(token_id)
    assert aruco_def.profile is None
    assert aruco_def.size == 3
    assert aruco_def.height_mm == 50.0
    assert aruco_def.height_mm == 50.0
