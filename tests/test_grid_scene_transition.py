import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import SceneId, ResultType, DetectionResult, MenuActions
from light_map.core.world_state import WorldState

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
    with patch("light_map.interactive_app.InteractiveApp._initialize_scenes") as mock_init, \
         patch("light_map.interactive_app.InteractiveApp._load_camera_calibration", return_value=(None, None, None, None)):
        scenes = {sid: MagicMock() for sid in SceneId}
        mock_init.return_value = scenes
        _app = InteractiveApp(config)
        return _app

def test_process_results_set_map_scale(app):
    # Setup initial scene
    app.current_scene = app.scenes[SceneId.MENU]
    
    # Create a result with SET_MAP_SCALE action
    result = DetectionResult(
        timestamp=12345,
        type=ResultType.ACTION,
        data={"action": MenuActions.SET_MAP_SCALE}
    )
    
    # Process the result
    transition = app._process_results([result])
    
    # Verify it returns a transition to CALIBRATE_MAP_GRID
    assert transition is not None
    assert transition.scene_id == SceneId.CALIBRATE_MAP_GRID

def test_process_results_calibrate_scale(app):
    # Setup initial scene
    app.current_scene = app.scenes[SceneId.MENU]
    
    # Create a result with CALIBRATE_SCALE action
    result = DetectionResult(
        timestamp=12345,
        type=ResultType.ACTION,
        data={"action": MenuActions.CALIBRATE_SCALE}
    )
    
    # Process the result
    transition = app._process_results([result])
    
    # Verify it returns a transition to CALIBRATE_MAP_GRID
    assert transition is not None
    assert transition.scene_id == SceneId.CALIBRATE_MAP_GRID
