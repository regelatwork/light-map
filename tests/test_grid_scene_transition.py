from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.core.common_types import MenuActions, SceneId
from light_map.interactive_app import AppConfig, InteractiveApp


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
    with (
        patch(
            "light_map.core.scene_manager.SceneManager._initialize_scenes"
        ) as mock_init,
        patch(
            "light_map.interactive_app.InteractiveApp._load_camera_calibration",
            return_value=(None, None, None, None),
        ),
    ):
        scenes = {sid: MagicMock() for sid in SceneId}
        mock_init.return_value = scenes
        _app = InteractiveApp(config)
        return _app


def test_process_results_set_map_scale(app):
    # Setup initial scene
    app.current_scene = app.scenes[SceneId.MENU]

    # Create a payload with SET_MAP_SCALE action
    payload = {"action": MenuActions.SET_MAP_SCALE}

    # Process the payload
    transition = app._handle_payloads(payload)

    # Verify it returns a transition to CALIBRATE_MAP_GRID
    assert transition is not None
    assert transition.target_scene == SceneId.CALIBRATE_MAP_GRID


def test_process_results_calibrate_scale(app):
    # Setup initial scene
    app.current_scene = app.scenes[SceneId.MENU]

    # Create a payload with CALIBRATE_SCALE action
    payload = {"action": MenuActions.CALIBRATE_SCALE}

    # Process the payload
    transition = app._handle_payloads(payload)

    # Verify it returns a transition to CALIBRATE_MAP_GRID
    assert transition is not None
    assert transition.target_scene == SceneId.CALIBRATE_MAP_GRID
