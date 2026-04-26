import pytest
from unittest.mock import MagicMock
from light_map.calibration.calibration_scenes import (
    ExtrinsicsCalibrationScene,
    PpiCalibrationScene,
    IntrinsicsCalibrationScene,
    FlashCalibrationScene,
    MapGridCalibrationScene,
    ProjectorCalibrationScene,
    Projector3DCalibrationScene,
)
from light_map.vision.scanning_scene import ScanningScene, ScanStage
from light_map.visibility.exclusive_vision_scene import ExclusiveVisionScene


@pytest.fixture
def mock_app():
    app = MagicMock()
    # scene_layer is removed
    app.aruco_mask_layer = MagicMock(name="aruco_mask_layer")
    app.hand_mask_layer = MagicMock(name="hand_mask_layer")
    app.token_layer = MagicMock(name="token_layer")
    app.menu_layer = MagicMock(name="menu_layer")
    app.notification_layer = MagicMock(name="notification_layer")
    app.debug_layer = MagicMock(name="debug_layer")
    app.selection_progress_layer = MagicMock(name="selection_progress_layer")
    app.cursor_layer = MagicMock(name="cursor_layer")
    app.map_layer = MagicMock(name="map_layer")
    app.map_grid_layer = MagicMock(name="map_grid_layer")
    app.calibration_layer = MagicMock(name="calibration_layer")
    app.flash_layer = MagicMock(name="flash_layer")
    app.door_layer = MagicMock(name="door_layer")
    app.fow_layer = MagicMock(name="fow_layer")
    app.visibility_layer = MagicMock(name="visibility_layer")
    app.exclusive_vision_layer = MagicMock(name="exclusive_vision_layer")
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
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.menu_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.cursor_layer in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_ppi_calibration_scene_layers(mock_app, mock_context):
    scene = PpiCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.menu_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_intrinsics_calibration_scene_layers(mock_app, mock_context):
    scene = IntrinsicsCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.menu_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_flash_calibration_scene_layers(mock_app, mock_context):
    scene = FlashCalibrationScene(mock_context)
    # Default stage (IDLE)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_map_grid_calibration_scene_layers(mock_app, mock_context):
    scene = MapGridCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.map_layer in layers
    assert mock_app.map_grid_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_projector_calibration_scene_layers(mock_app, mock_context):
    scene = ProjectorCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert mock_app.calibration_layer in layers
    assert mock_app.token_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer not in layers
    assert mock_app.selection_progress_layer not in layers
    assert mock_app.aruco_mask_layer not in layers
    assert mock_app.hand_mask_layer not in layers


def test_projector_3d_calibration_scene_layers(mock_app, mock_context):
    # This test was missing in the previous version of the test file
    scene = Projector3DCalibrationScene(mock_context)
    layers = scene.get_active_layers(mock_app)
    assert scene.pattern_layer in layers
    assert scene.feedback_layer in layers
    assert mock_app.calibration_layer not in layers
    assert mock_app.notification_layer in layers
    assert mock_app.cursor_layer in layers

    assert mock_app.selection_progress_layer not in layers
    assert mock_app.cursor_layer in layers


def test_scanning_scene_layers(mock_app, mock_context):
    scene = ScanningScene(mock_context)
    # Default stage is START, which is NOT SHOW_RESULT or DONE
    layers = scene.get_active_layers(mock_app)
    assert mock_app.flash_layer in layers
    assert mock_app.calibration_layer in layers
    assert mock_app.aruco_mask_layer in layers
    assert mock_app.hand_mask_layer in layers
    assert mock_app.notification_layer not in layers
    assert mock_app.debug_layer in layers
    assert mock_app.cursor_layer in layers

    # Test SHOW_RESULT stage
    scene._stage = ScanStage.SHOW_RESULT
    mock_app.layer_stack = [
        mock_app.map_layer,
        mock_app.notification_layer,
        mock_app.debug_layer,
    ]
    layers = scene.get_active_layers(mock_app)
    assert mock_app.map_layer in layers
    assert mock_app.debug_layer in layers
    assert (
        mock_app.notification_layer not in layers
    )  # EXPLICITLY excluded in SHOW_RESULT


def test_exclusive_vision_scene_layers(mock_app, mock_context):
    mock_context.layer_manager = mock_app
    mock_context.inspected_token_mask = None
    scene = ExclusiveVisionScene(mock_context)
    layers = scene.get_active_layers(mock_app)

    assert mock_app.background_composite in layers
    assert mock_app.map_layer not in layers  # Collapsed into composite
    assert mock_app.door_layer not in layers
    assert mock_app.fow_layer not in layers
    assert mock_app.visibility_layer not in layers
    assert mock_app.notification_layer in layers  # INCLUDED in ExclusiveVisionScene
    assert mock_app.debug_layer in layers
    assert mock_app.cursor_layer in layers
