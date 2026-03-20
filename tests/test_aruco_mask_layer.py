import numpy as np
import pytest
import cv2
from unittest.mock import MagicMock
from light_map.aruco_mask_layer import ArucoMaskLayer
from light_map.common_types import AppConfig
from light_map.core.world_state import WorldState
from light_map.vision.projection import CameraProjectionModel


@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.width = 4000
    config.height = 4000
    config.enable_aruco_masking = True
    config.aruco_mask_padding = 10
    config.projector_matrix = np.eye(3)
    config.distortion_model = None
    config.camera_matrix = None
    config.rotation_vector = None
    config.translation_vector = None
    config.projector_ppi = 25.4  # 1mm = 1px for simple tests
    config.token_profiles = {}
    config.aruco_defaults = {}
    config.storage_manager = None
    config.projector_3d_model = None
    config.projector_matrix_resolution = (10000, 10000)
    config.camera_projection_model = None
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
    assert v1 == (mock_state.raw_aruco_timestamp << 1) | 1

    # Disabled
    mock_config.enable_aruco_masking = False
    v2 = layer.get_current_version()
    assert v2 == (mock_state.raw_aruco_timestamp << 1) | 0

    # Tokens updated (Should NOT affect raw_aruco_timestamp)
    mock_state.tokens_timestamp = 2
    v3 = layer.get_current_version()
    assert v3 == (mock_state.raw_aruco_timestamp << 1) | 0

    # Raw ArUco updated
    mock_state.raw_aruco_timestamp = 3
    v4 = layer.get_current_version()
    assert v4 == (3 << 1) | 0


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


def test_aruco_mask_layer_parallax_rendering(mock_state, mock_config):
    """Verifies that height changes the projection coordinates (parallax)."""
    # 1. Setup camera calibration (Looking down from Z=1000)
    mock_config.camera_matrix = np.array(
        [[1000, 0, 960], [0, 1000, 540], [0, 0, 1]], dtype=np.float32
    )
    # Camera at (0, 0, 1000) in world, looking down
    rotation_matrix = np.array(
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float32
    )
    mock_config.rotation_vector, _ = cv2.Rodrigues(rotation_matrix)
    mock_config.translation_vector = np.array([[0], [0], [1000]], dtype=np.float32)

    mock_config.projector_ppi = 25.4  # 1mm = 1px
    mock_config.projector_matrix_resolution = (10000, 10000)

    # Marker corners in camera space
    corners = np.array(
        [[1010, 490], [1110, 490], [1110, 590], [1010, 590]], dtype=np.float32
    )
    mock_state.raw_aruco = {"corners": [corners], "ids": [42]}

    from dataclasses import dataclass

    @dataclass
    class Profile:
        height_mm: float

    @dataclass
    class Default:
        profile: str

    mock_config.token_profiles = {"standard": Profile(height_mm=0.0)}
    mock_config.aruco_defaults = {42: Default(profile="standard")}

    # Initialize projection model
    mock_config.camera_projection_model = CameraProjectionModel(
        mock_config.camera_matrix,
        np.zeros(5),
        mock_config.rotation_vector,
        mock_config.translation_vector,
    )
    # Also need Projector3DModel and ProjectionService for it to work
    from light_map.vision.projection import Projector3DModel, ProjectionService
    mock_config.projector_3d_model = Projector3DModel(
        homography_matrix=np.eye(3), # Identity for simplicity in this test
        use_3d=False # If False, it uses homography but ProjectionService still passes height to Camera model
    )
    projection_service = ProjectionService(mock_config.camera_projection_model, mock_config.projector_3d_model)

    layer = ArucoMaskLayer(mock_state, mock_config, projection_service=projection_service)

    # Height 0mm
    patches_0 = layer._generate_patches(0.0)
    assert len(patches_0) == 1
    x0 = patches_0[0].x

    # Height 100mm
    mock_config.token_profiles["standard"].height_mm = 100.0
    patches_100 = layer._generate_patches(0.0)
    x100 = patches_100[0].x

    assert x100 < x0
