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
    config.projector_ppi = 100.0
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

            patches = layer.render(current_time=0.0)

            assert len(patches) > 0
            p = patches[0]
            # localized patches won't be full screen
            assert p.width < 1920
            assert p.height < 1080
            # Check alpha channel exists and has some visibility
            assert p.data.shape[2] == 4
            assert np.any(p.data[:, :, 3] > 0)


def test_hand_mask_layer_disabled(mock_config):
    mock_config.enable_hand_masking = False
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1

    layer = HandMaskLayer(ws, mock_config)
    patches = layer.render(current_time=0.0)
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

            p1 = layer.render(current_time=0.0)
            p2 = layer.render(current_time=0.0)

            assert p1 is p2
            assert mock_hulls.call_count == 1

            # Change timestamp
            from light_map.core.scene import HandInput
            from light_map.common_types import GestureType

            new_input = [HandInput(GestureType.POINTING, (100, 100), (0.0, 0.0), None)]
            ws.update_inputs(new_input)  # increments hands_timestamp
            p3 = layer.render(current_time=0.1)
            assert p3 is not p1
            assert mock_hulls.call_count == 2


def test_hand_mask_expansion_with_ppi():
    # Setup config with a known PPI
    config = AppConfig(
        width=1000,
        height=1000,
        projector_matrix=np.eye(3),
        enable_hand_masking=True,
        hand_mask_padding=0,  # This shouldn't affect the mask shape anymore
        hand_mask_blur=0,
        projector_ppi=100.0,
    )

    ws = WorldState()
    # Mock background for shape
    ws.background = np.zeros((1000, 1000, 3), dtype=np.uint8)

    # Mock a single hand with 3 points forming a triangle
    # Points are in normalized camera coordinates (0 to 1)
    ws.hands = [[{"x": 0.5, "y": 0.5}, {"x": 0.55, "y": 0.5}, {"x": 0.5, "y": 0.55}]]
    ws.hands_timestamp = 1

    layer = HandMaskLayer(ws, config)

    # Generate patches
    patches = layer._generate_patches(current_time=0.0)

    assert len(patches) == 1
    patch = patches[0]

    # 2cm at 100 PPI is 0.7874 * 100 = 78.74 pixels -> 78 pixels
    # The triangle sides are 0.05 * 1000 = 50 pixels.
    # Without expansion, the mask would be a triangle of 50x50 area / 2 = 1250 pixels.
    # With 78px expansion, it should be much larger.

    mask = patch.data[:, :, 3]
    mask_area = np.sum(mask > 0)

    # triangle area is small, but expanded area should be at least a circle of radius 78px
    # Area of circle R=78 is pi * 78^2 = 3.14 * 6084 = 19103
    assert mask_area > 15000

    # If we set PPI to 0, it should be much smaller
    config.projector_ppi = 0.0
    patches_no_ppi = layer._generate_patches(current_time=0.0)
    mask_no_ppi = patches_no_ppi[0].data[:, :, 3]
    mask_area_no_ppi = np.sum(mask_no_ppi > 0)

    assert (
        mask_area_no_ppi < 2000
    )  # Just the triangle + small margin for bounding box logic
    assert mask_area > mask_area_no_ppi * 10


def test_hand_mask_persistence():
    config = AppConfig(
        width=1000,
        height=1000,
        projector_matrix=np.eye(3),
        enable_hand_masking=True,
        projector_ppi=100.0,
    )
    ws = WorldState()
    layer = HandMaskLayer(ws, config)

    # No hands initially
    assert len(layer._generate_patches(current_time=0.0)) == 0

    # Add hand at t=0
    ws.hands = [[{"x": 0.5, "y": 0.5}]]
    ws.hands_timestamp = 1
    assert len(layer._generate_patches(current_time=0.0)) == 1

    # Remove hand immediately at t=0
    ws.hands = []
    ws.hands_timestamp = 2
    # Should still be present because persistence_seconds=1.0 (default)
    assert len(layer._generate_patches(current_time=0.5)) == 1

    # Should disappear at t=1.1
    assert len(layer._generate_patches(current_time=1.1)) == 0
