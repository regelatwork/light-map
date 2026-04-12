import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from light_map.rendering.layers.hand_mask_layer import HandMaskLayer
from light_map.state.world_state import WorldState
from light_map.core.common_types import AppConfig


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.enable_hand_masking = True
    config.width = 1920
    config.height = 1080
    config.hand_mask_padding = 10
    config.projector_matrix = np.eye(3)
    config.projector_ppi = 100.0
    config.distortion_model = None
    return config


def test_hand_mask_layer_render_enabled(mock_config):
    ws = WorldState()
    # Mock some hands
    ws.hands = [
        [{"x": 0.5, "y": 0.5}, {"x": 0.6, "y": 0.6}]
    ]  # dummy landmarks (triggers hands_version)

    # We need to mock the transform_pts logic
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)  # dummy frame for shape

    layer = HandMaskLayer(ws, mock_config)

    # Mock HandMasker internals to avoid CV2 calls
    with patch.object(layer.hand_masker, "get_mask_hulls") as mock_hulls:
        mock_hulls.return_value = [
            np.array([[50, 50], [60, 50], [60, 60]], dtype=np.int32)
        ]

        patches = layer.render(current_time=0.0)[0]

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
    ws.hands = [[{"x": 0.5, "y": 0.5}]]  # Triggers hands_version

    layer = HandMaskLayer(ws, mock_config)
    patches = layer.render(current_time=0.0)[0]
    assert len(patches) == 0


def test_hand_mask_layer_caching(mock_config):
    ws = WorldState()
    ws.hands = [[{"x": 0.5, "y": 0.5}]]  # Triggers hands_version
    ws.background = np.zeros((100, 100, 3), dtype=np.uint8)

    layer = HandMaskLayer(ws, mock_config)

    with patch.object(layer.hand_masker, "get_mask_hulls") as mock_hulls:
        mock_hulls.return_value = [np.array([[50, 50], [60, 60]])]

        p1 = layer.render(current_time=0.0)[0]
        p2 = layer.render(current_time=0.0)[0]

        assert p1 is p2
        assert mock_hulls.call_count == 1

        # Change timestamp
        from light_map.core.scene import HandInput
        from light_map.core.common_types import GestureType

        new_input = [HandInput(GestureType.POINTING, (100, 100), (0.0, 0.0), None)]
        ws.update_inputs(new_input)  # increments hands_version
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
        projector_ppi=100.0,
    )

    ws = WorldState()
    # Mock background for shape
    ws.background = np.zeros((1000, 1000, 3), dtype=np.uint8)

    # Mock a single hand with 3 points forming a triangle
    # Points are in normalized camera coordinates (0 to 1)
    ws.hands = [
        [{"x": 0.5, "y": 0.5}, {"x": 0.55, "y": 0.5}, {"x": 0.5, "y": 0.55}]
    ]  # Triggers hands_version

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
    ws.hands = [[{"x": 0.5, "y": 0.5}]]  # Triggers hands_version
    assert len(layer._generate_patches(current_time=0.0)) == 1

    # Remove hand immediately at t=0
    ws.hands = []  # Triggers hands_version
    # Should still be present because persistence_seconds=1.0 (default)
    assert len(layer._generate_patches(current_time=0.5)) == 1

    # Should disappear at t=1.1
    assert len(layer._generate_patches(current_time=1.1)) == 0


def test_hand_mask_layer_version_with_persistence(mock_config):
    """Verifies that version updates every frame ONLY during lingering."""
    ws = WorldState()
    layer = HandMaskLayer(ws, mock_config)

    # 1. Initial detection (add hand at t=0)
    ws.hands = [[{"x": 0.5, "y": 0.5}]]  # Triggers hands_version
    layer._generate_patches(current_time=0.0)
    v_base = layer.get_current_version()

    # Update system time - should NOT affect version because no lingering yet
    ws._system_time_atom.update(0.1, force_timestamp=ws.hands_version + 1000)
    v1 = layer.get_current_version()
    assert v1 == v_base  # Still based on hands_version

    # 2. Lost detection (hand gone, but lingering in masker)
    ws.hands = []  # Triggers hands_version
    v_after_lost = layer.get_current_version()

    # system_time_version should now trigger every-frame updates
    ws._system_time_atom.update(0.5, force_timestamp=ws.hands_version + 2000)
    v2 = layer.get_current_version()
    assert v2 > v_after_lost

    # 3. After persistence expires
    layer._generate_patches(current_time=1.5)  # This will clear last_hulls
    v3 = layer.get_current_version()

    # Update system time again - should NOT affect version
    ws._system_time_atom.update(1.6, force_timestamp=v3 + 1000)
    v4 = layer.get_current_version()
    assert v4 == v3
