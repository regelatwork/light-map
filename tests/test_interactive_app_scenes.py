from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.core.common_types import SceneId
from light_map.core.scene import SceneTransition
from light_map.interactive_app import AppConfig, InteractiveApp
from light_map.state.world_state import WorldState


@pytest.fixture
def app(tmp_path):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))
    matrix = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=100,
        height=100,
        projector_matrix=matrix,
        map_search_patterns=[],
        storage_manager=storage,
    )
    # Patch all scenes to avoid complex initialization
    with (
        patch(
            "light_map.core.scene_manager.SceneManager._initialize_scenes"
        ) as mock_init,
        patch(
            "light_map.interactive_app.InteractiveApp._load_camera_calibration",
            return_value=(
                np.eye(3),
                np.zeros(5),
                np.zeros((3, 1)),
                np.zeros((3, 1)),
            ),
        ),
    ):
        # Create mock scenes for all SceneIds
        scenes = {sid: MagicMock() for sid in SceneId}
        mock_init.return_value = scenes
        _app = InteractiveApp(config)
        return _app


def test_switch_scene_logic(app):
    # Setup initial scene
    initial_scene = app.scenes[SceneId.MENU]
    app.current_scene = initial_scene

    # Target scene
    target_scene = app.scenes[SceneId.MAP]
    payload = {"foo": "bar"}
    transition = SceneTransition(SceneId.MAP, payload=payload)

    # Perform switch
    app._switch_scene(transition)

    # Verify on_exit was called on initial scene
    initial_scene.on_exit.assert_called_once()

    # Verify current_scene updated
    assert app.current_scene == target_scene

    # Verify on_enter was called on target scene with payload
    target_scene.on_enter.assert_called_once_with(payload)


def test_switch_scene_invalid_id(app):
    initial_scene = app.scenes[SceneId.MENU]
    app.current_scene = initial_scene

    # Use an invalid SceneId (mocking one that isn't in app.scenes)
    # Actually SceneId is an Enum, so let's just remove one from app.scenes
    del app.scenes[SceneId.SCANNING]

    transition = SceneTransition(SceneId.SCANNING)

    with patch("logging.error") as mock_log:
        app._switch_scene(transition)
        mock_log.assert_called_once()

    # Should still be in initial scene
    assert app.current_scene == initial_scene


def test_process_state_triggers_switch(app):
    app.current_scene = app.scenes[SceneId.MENU]

    # Setup transition to be returned by update
    transition = SceneTransition(SceneId.VIEWING)
    app.current_scene.update.return_value = transition

    # Setup mock for _switch_scene
    app._switch_scene = MagicMock()

    # Mock other methods to avoid side effects
    app.input_processor.convert_mediapipe_to_inputs = MagicMock(return_value=[])

    app.current_scene.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    state = WorldState()
    state.background = frame
    state.last_frame_timestamp = 1
    app.process_state(state, [])

    # Verify _switch_scene was called
    app._switch_scene.assert_called_once_with(transition)


def test_process_state_layer_filtering(app):
    """Verifies that process_state uses the scene's requested layer stack."""
    # Setup scene and its active layers
    current_scene = MagicMock()
    mock_layer = MagicMock()
    current_scene.get_active_layers.return_value = [mock_layer]
    app.current_scene = current_scene

    # Mock renderer to verify what layers it receives
    app.renderer.render = MagicMock(
        return_value=np.zeros((100, 100, 3), dtype=np.uint8)
    )

    # Mock other methods to avoid side effects
    app.input_processor.convert_mediapipe_to_inputs = MagicMock(return_value=[])
    current_scene.update.return_value = None

    state = WorldState()
    app.process_state(state, [])

    # Verify renderer.render was called with the scene's requested layers
    # (The state is the first argument, current_time the third, instrument fourth)
    args, kwargs = app.renderer.render.call_args
    assert args[1] == [mock_layer]
