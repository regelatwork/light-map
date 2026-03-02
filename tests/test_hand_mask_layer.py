import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.hand_mask_layer import HandMaskLayer
from light_map.core.world_state import WorldState
from light_map.common_types import AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 100
    config.height = 100
    config.enable_hand_masking = True
    config.hand_mask_padding = 5
    config.hand_mask_blur = 3
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    return config


def test_hand_mask_layer_render_enabled(mock_config):
    ws = WorldState()
    # Mock some hands
    ws.hands = [[{"x": 0.5, "y": 0.5}, {"x": 0.6, "y": 0.6}]]  # dummy landmarks
    ws.hands_timestamp = 1

    # We need to mock the transform_pts logic or provide a dummy last_camera_frame
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)  # dummy frame for shape

    layer = HandMaskLayer(mock_config)
    patches = layer.render(ws)

    assert len(patches) == 1
    patch = patches[0]
    assert patch.width == 100
    assert patch.height == 100
    # At least some pixels should be opaque black (if the hand masker worked)
    # Since we use real HandMasker inside, we expect it to draw something.
    assert np.any(patch.data[:, :, 3] == 255)
    # Check that where it is opaque, it is black
    mask = patch.data[:, :, 3] == 255
    assert np.all(patch.data[mask, :3] == 0)


def test_hand_mask_layer_disabled(mock_config):
    mock_config.enable_hand_masking = False
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1

    layer = HandMaskLayer(mock_config)
    patches = layer.render(ws)
    assert len(patches) == 0


def test_hand_mask_layer_caching(mock_config):
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)

    layer = HandMaskLayer(mock_config)
    layer.render(ws)
    assert layer.last_rendered_timestamp == 1

    # Re-render with same timestamp
    layer.render(ws)
    assert layer.last_rendered_timestamp == 1
    # Check that HandMasker.compute_hulls was only called once?
    # Hard to check without mocking HandMasker.
