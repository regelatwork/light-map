import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.state.world_state import WorldState
from light_map.core.common_types import SceneId


@pytest.fixture
def app_with_real_scenes(tmp_path):
    """App with real scenes but mocked peripherals."""
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
            "light_map.interactive_app.InteractiveApp._load_camera_calibration",
            return_value=(
                np.eye(3),
                np.zeros(5),
                np.zeros((3, 1)),
                np.zeros((3, 1)),
            ),
        ),
        patch(
            "light_map.map.map_config.MapConfigManager._load", return_value=MagicMock()
        ),
    ):
        _app = InteractiveApp(config)
        return _app


def test_process_state_returns_valid_image(app_with_real_scenes):
    # Setup
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    state = WorldState()
    state.background = frame
    state.last_frame_timestamp = 1

    # Mock input processor to return empty inputs
    app_with_real_scenes.input_processor.convert_mediapipe_to_inputs = MagicMock(
        return_value=[]
    )

    # Execute
    output_image, actions = app_with_real_scenes.process_state(state, [])

    # Verify
    assert output_image is not None, (
        "process_state returned None, which causes cv2.imshow to fail."
    )
    assert isinstance(output_image, np.ndarray)
    assert output_image.shape == (100, 100, 3)
    assert output_image.dtype == np.uint8


def test_map_render_caching(app_with_real_scenes):
    """Verifies that the map is only re-rendered when state actually changes."""
    # 1. Setup Map
    mock_loader = MagicMock()
    mock_loader.render.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    app_with_real_scenes.map_system.svg_loader = mock_loader

    # Switch to ViewingScene so base layer is rendered
    app_with_real_scenes.current_scene = app_with_real_scenes.scenes[SceneId.VIEWING]

    # 2. Mock state and inputs
    state = WorldState()
    state.background = np.zeros((100, 100, 3), dtype=np.uint8)
    app_with_real_scenes.input_processor.convert_mediapipe_to_inputs = MagicMock(
        return_value=[]
    )

    # 3. First render (should call svg_loader.render)
    app_with_real_scenes.process_state(state, [])
    assert mock_loader.render.call_count == 1

    # 4. Second render with same state (should NOT call svg_loader.render)
    app_with_real_scenes.process_state(state, [])
    assert mock_loader.render.call_count == 1

    # 5. Change Map State (Pan)
    app_with_real_scenes.map_system.pan(10, 0)
    app_with_real_scenes.process_state(state, [])
    assert mock_loader.render.call_count == 2

    # 6. Same state again
    app_with_real_scenes.process_state(state, [])
    assert mock_loader.render.call_count == 2
