import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import SceneId

@pytest.fixture
def app_with_real_scenes():
    """App with real scenes but mocked peripherals."""
    matrix = np.eye(3, dtype=np.float32)
    config = AppConfig(
        width=100, height=100, projector_matrix=matrix, map_search_patterns=[]
    )
    
    with patch("light_map.interactive_app.InteractiveApp._load_camera_calibration", return_value=(None, None)):
        with patch("light_map.map_config.MapConfigManager._load", return_value=MagicMock()):
            _app = InteractiveApp(config)
            return _app

def test_process_frame_returns_valid_image(app_with_real_scenes):
    # Setup
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MagicMock()
    results.multi_hand_landmarks = None
    
    # Mock input processor to return empty inputs
    app_with_real_scenes.input_processor.convert_mediapipe_to_inputs = MagicMock(return_value=[])
    
    # Execute
    output_image, actions = app_with_real_scenes.process_frame(frame, results)
    
    # Verify
    assert output_image is not None, "process_frame returned None, which causes cv2.imshow to fail."
    assert isinstance(output_image, np.ndarray)
    assert output_image.shape == (100, 100, 3)
    assert output_image.dtype == np.uint8
