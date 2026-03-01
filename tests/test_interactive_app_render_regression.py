import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.core.world_state import WorldState


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
            return_value=(None, None, None, None),
        ),
        patch("light_map.map_config.MapConfigManager._load", return_value=MagicMock()),
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
