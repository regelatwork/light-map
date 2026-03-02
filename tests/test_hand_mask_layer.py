import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from light_map.hand_mask_layer import HandMaskLayer
from light_map.core.world_state import WorldState
from light_map.common_types import AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.enable_hand_masking = True
    config.width = 1920
    config.height = 1080
    config.hand_mask_padding = 10
    config.hand_mask_blur = 5
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    return config


def test_hand_mask_layer_render_enabled(mock_config):
    ws = WorldState()
    # Mock some hands
    ws.hands = [[{"x": 0.5, "y": 0.5}, {"x": 0.6, "y": 0.6}]]  # dummy landmarks
    ws.hands_timestamp = 1

    # We need to mock the transform_pts logic
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)  # dummy frame for shape

    layer = HandMaskLayer(ws, mock_config)

    # Mock HandMasker internals to avoid CV2 calls
    with patch.object(layer.hand_masker, "compute_hulls") as mock_hulls:
        mock_hulls.return_value = [
            np.array([[0, 0], [10, 0], [10, 10]], dtype=np.int32)
        ]
        with patch.object(layer.hand_masker, "generate_mask_image") as mock_mask:
            # Return a small white square on black
            dummy_mask = np.zeros((1080, 1920), dtype=np.uint8)
            dummy_mask[0:10, 0:10] = 255
            mock_mask.return_value = dummy_mask

            patches = layer.render()

            assert len(patches) == 1
            p = patches[0]
            assert p.x == 0
            assert p.y == 0
            assert p.width == 1920
            assert p.height == 1080
            # Check alpha channel
            assert np.array_equal(p.data[5, 5], [0, 0, 0, 255])
            assert np.array_equal(p.data[20, 20], [0, 0, 0, 0])


def test_hand_mask_layer_disabled(mock_config):
    mock_config.enable_hand_masking = False
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1

    layer = HandMaskLayer(ws, mock_config)
    patches = layer.render()
    assert len(patches) == 0


def test_hand_mask_layer_caching(mock_config):
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)

    layer = HandMaskLayer(ws, mock_config)

    with patch.object(layer.hand_masker, "compute_hulls") as mock_hulls:
        mock_hulls.return_value = [np.array([[0, 0], [1, 1]])]
        with patch.object(layer.hand_masker, "generate_mask_image") as mock_mask:
            mock_mask.return_value = np.zeros((1080, 1920), dtype=np.uint8)

            p1 = layer.render()
            p2 = layer.render()

            assert p1 is p2
            assert mock_hulls.call_count == 1

            # Change timestamp
            from light_map.core.scene import HandInput
            from light_map.common_types import GestureType

            new_input = [HandInput(GestureType.POINTING, (100, 100), None)]
            ws.update_inputs(new_input)  # increments hands_timestamp
            p3 = layer.render()
            assert p3 is not p1
            assert mock_hulls.call_count == 2
