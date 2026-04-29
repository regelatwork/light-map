import os
from unittest.mock import MagicMock

import numpy as np
import pytest

from light_map.core.common_types import AppConfig
from light_map.interactive_app import InteractiveApp


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


def test_interactive_app_delete_token_override_action(
    mock_config, monkeypatch, tmp_path
):
    # Setup MapConfig to use a temporary file
    map_state_file = tmp_path / "map_state.json"
    tokens_file = tmp_path / "tokens.json"

    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    app.map_config.filename = str(map_state_file)
    app.map_config.tokens_filename = str(tokens_file)
    app.map_config.save()

    ws = app.state
    app.current_map_path = os.path.abspath("test_map.svg")

    # 1. Setup global default
    token_id = 123
    app.map_config.set_global_aruco_definition(
        aruco_id=token_id, name="Global Name", color="#ff0000"
    )

    # 2. Setup map override
    app.map_config.set_map_aruco_override(
        map_name=app.current_map_path,
        aruco_id=token_id,
        name="Map Override Name",
        color="#0000ff",
    )

    # Verify override exists
    resolved = app.map_config.resolve_token_profile(token_id, app.current_map_path)
    assert resolved.name == "Map Override Name"
    assert resolved.color == "#0000ff"

    # 3. Inject DELETE_TOKEN_OVERRIDE action
    ws.pending_actions.append({"action": "DELETE_TOKEN_OVERRIDE", "id": token_id})

    # We need to mock the current scene's render/update
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.side_effect = lambda f: (f, 1)

    app.process_state(ws, [])

    # 4. Verify override is deleted and falls back to global
    resolved_after = app.map_config.resolve_token_profile(
        token_id, app.current_map_path
    )
    assert resolved_after.name == "Global Name"
    assert resolved_after.color == "#ff0000"

    # Verify it's gone from the config data
    map_entry = app.map_config.data.maps.get(app.current_map_path)
    assert token_id not in map_entry.aruco_overrides


def test_interactive_app_delete_global_token_action(mock_config, monkeypatch, tmp_path):
    # Setup MapConfig to use a temporary file
    tokens_file = tmp_path / "tokens.json"

    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)
    app.map_config.tokens_filename = str(tokens_file)
    app.map_config.save()

    ws = app.state

    # 1. Setup global default
    token_id = 456
    app.map_config.set_global_aruco_definition(
        aruco_id=token_id, name="To Be Deleted", color="#00ff00"
    )

    # Verify definition exists
    assert token_id in app.map_config.data.global_settings.aruco_defaults

    # 2. Inject DELETE_TOKEN action
    ws.pending_actions.append({"action": "DELETE_TOKEN", "id": token_id})

    # Mock scene
    app.current_scene = MagicMock()
    app.current_scene.version = 1
    app.current_scene.update.return_value = None
    app.current_scene.get_active_layers.return_value = app.layer_stack
    app.current_scene.render.side_effect = lambda f: (f, 1)

    app.process_state(ws, [])

    # 3. Verify definition is deleted
    assert token_id not in app.map_config.data.global_settings.aruco_defaults
