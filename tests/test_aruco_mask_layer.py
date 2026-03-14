import numpy as np
import pytest
from unittest.mock import MagicMock
from light_map.aruco_mask_layer import ArucoMaskLayer
from light_map.common_types import AppConfig
from light_map.core.world_state import WorldState


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    config.enable_aruco_masking = True
    config.aruco_mask_padding = 10
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    return config


@pytest.fixture
def mock_state():
    state = WorldState()
    state.tokens_timestamp = 1
    # Mock some ArUco corners in camera space
    # Marker 1: Top-left square
    corners1 = np.array(
        [[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32
    )
    state.raw_aruco = {"corners": [corners1], "ids": [42]}
    return state


def test_aruco_mask_layer_version(mock_state, mock_config):
    layer = ArucoMaskLayer(mock_state, mock_config)

    # Enabled
    mock_config.enable_aruco_masking = True
    v1 = layer.get_current_version()
    assert v1 == (mock_state.tokens_timestamp << 1) | 1

    # Disabled
    mock_config.enable_aruco_masking = False
    v2 = layer.get_current_version()
    assert v2 == (mock_state.tokens_timestamp << 1) | 0

    # Tokens updated
    mock_state.tokens_timestamp = 2
    v3 = layer.get_current_version()
    assert v3 == (mock_state.tokens_timestamp << 1) | 0


def test_aruco_mask_layer_rendering(mock_state, mock_config):
    layer = ArucoMaskLayer(mock_state, mock_config)

    patches = layer._generate_patches(0.0)

    assert len(patches) == 1
    patch = patches[0]

    # Check bounding box
    # corners are [100, 100] to [200, 200]
    # pad is 10
    # Expected: x=90, y=90, w=120, h=120
    assert patch.x == 90
    assert patch.y == 90
    assert (
        patch.width == 121
    )  # 100 + 10 + 10 + 1 (boundingRect inclusive/exclusive nuances)
    assert patch.height == 121

    # Check data
    assert patch.data.shape == (121, 121, 4)
    # Center of patch should be grey (128, 128, 128)
    # Patch center in local coords is around (60, 60)
    center_pixel = patch.data[60, 60]
    assert np.array_equal(center_pixel[:3], [128, 128, 128])
    assert center_pixel[3] == 255


def test_aruco_mask_layer_disabled(mock_state, mock_config):
    mock_config.enable_aruco_masking = False
    layer = ArucoMaskLayer(mock_state, mock_config)

    patches = layer._generate_patches(0.0)
    assert len(patches) == 0


def test_aruco_mask_layer_no_aruco(mock_state, mock_config):
    mock_state.raw_aruco = {"corners": [], "ids": []}
    layer = ArucoMaskLayer(mock_state, mock_config)

    patches = layer._generate_patches(0.0)
    assert len(patches) == 0


def test_aruco_mask_layer_list_corners(mock_state, mock_config):
    """Verifies that the layer correctly handles corners as lists (common after IPC)."""
    # corners as list of lists instead of numpy array
    corners_list = [[100.0, 100.0], [200.0, 100.0], [200.0, 200.0], [100.0, 200.0]]
    mock_state.raw_aruco = {"corners": [corners_list], "ids": [42]}
    layer = ArucoMaskLayer(mock_state, mock_config)

    # This should not raise AttributeError: 'list' object has no attribute 'reshape'
    patches = layer._generate_patches(0.0)
    assert len(patches) == 1
    assert patches[0].x == 90
