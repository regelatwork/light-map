import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp
from light_map.common_types import AppConfig
from light_map.core.world_state import WorldState


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
    config.hand_mask_blur = 0
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
    assert len(app.layer_stack) == 5
    assert app.renderer.output_buffer.shape == (100, 100, 3)


def test_interactive_app_process_state_layered(mock_config, monkeypatch):
    monkeypatch.setattr(
        InteractiveApp,
        "_load_camera_calibration",
        lambda self: (np.eye(3), np.zeros(5), np.zeros(3), np.zeros(3)),
    )

    app = InteractiveApp(mock_config)

    ws = WorldState()
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
