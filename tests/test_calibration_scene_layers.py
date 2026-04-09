import pytest
from unittest.mock import MagicMock
from light_map.calibration.calibration_scenes import (
    ExtrinsicsCalibrationScene,
    PpiCalibrationScene,
    IntrinsicsCalibrationScene,
    FlashCalibrationScene,
    MapGridCalibrationScene,
    ProjectorCalibrationScene,
)


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.scene_layer = MagicMock(name="scene_layer")
    app.aruco_mask_layer = MagicMock(name="aruco_mask_layer")
    app.hand_mask_layer = MagicMock(name="hand_mask_layer")
    app.token_layer = MagicMock(name="token_layer")
    app.menu_layer = MagicMock(name="menu_layer")
    app.notification_layer = MagicMock(name="notification_layer")
    app.debug_layer = MagicMock(name="debug_layer")
    app.selection_progress_layer = MagicMock(name="selection_progress_layer")
    app.cursor_layer = MagicMock(name="cursor_layer")
    app.map_layer = MagicMock(name="map_layer")
    return app


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.app_config = MagicMock()
    context.map_config_manager = MagicMock()
    context.events = MagicMock()
    context.notifications = MagicMock()
    context.state = MagicMock()
    return context


def test_extrinsics_calibration_scene_layers(mock_app, mock_context):
    scene = ExtrinsicsCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    # Corrected behavior: should NOT include aruco_mask_layer
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_ppi_calibration_scene_layers(mock_app, mock_context):
    scene = PpiCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_intrinsics_calibration_scene_layers(mock_app, mock_context):
    scene = IntrinsicsCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_flash_calibration_scene_layers(mock_app, mock_context):
    scene = FlashCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_map_grid_calibration_scene_layers(mock_app, mock_context):
    scene = MapGridCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers
    assert mock_app.map_layer in layers


def test_projector_calibration_scene_layers(mock_app, mock_context):
    # This one already excludes it
    scene = ProjectorCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers
