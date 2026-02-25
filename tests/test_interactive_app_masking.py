import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.interactive_app import InteractiveApp, AppConfig


@pytest.fixture
def app(tmp_path):
    from light_map.core.storage import StorageManager

    storage = StorageManager(base_dir=str(tmp_path))
    config = AppConfig(
        width=100,
        height=100,
        projector_matrix=np.eye(3),
        enable_hand_masking=True,
        hand_mask_padding=0,
        hand_mask_blur=0,
        storage_manager=storage,
    )
    return InteractiveApp(config)


def test_apply_hand_masking_blacks_out_region(app):
    # Create a white frame
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 255

    # Mock MediaPipe results with one hand
    results = MagicMock()
    landmark = MagicMock()
    # 0.5, 0.5 is (50, 50) in 100x100
    landmark.x = 0.5
    landmark.y = 0.5

    hand_landmarks = MagicMock()
    hand_landmarks.landmark = [landmark] * 21
    results.multi_hand_landmarks = [hand_landmarks]

    # Set last_camera_frame so transformation works
    app.app_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    masked_frame = app._apply_hand_masking(frame, results)

    # Check that (50, 50) is black (or near it due to hull)
    assert np.all(masked_frame[50, 50] == 0)
    # Check that (10, 10) is still white
    assert np.all(masked_frame[10, 10] == 255)


def test_apply_hand_masking_disabled(app):
    app.config.enable_hand_masking = False
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 255
    results = MagicMock()  # with landmarks

    masked_frame = app._apply_hand_masking(frame, results)
    assert np.all(masked_frame == 255)
