import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.calibration.calibration_scenes import ExtrinsicsCalibrationScene
from light_map.core.scene import HandInput
from light_map.input.gestures import GestureType


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.app_config.width = 1920
    context.app_config.height = 1080
    context.map_config_manager.get_ppi.return_value = 100.0  # Use 100 PPI for easy math
    context.app_config.projector_ppi = 100.0

    # Mock global settings and resolve_token_profile
    context.map_config_manager.data.global_settings.aruco_defaults = {
        10: MagicMock(profile="medium"),
        11: MagicMock(profile="medium"),
        12: MagicMock(profile="medium"),
    }

    def mock_resolve(aid, map_name=None):
        mock_token = MagicMock()
        mock_token.height_mm = 25.0
        mock_token.name = f"Token {aid}"
        mock_token.size = 1  # 1x1 inch
        return mock_token

    context.map_config_manager.resolve_token_profile.side_effect = mock_resolve
    context.app_config.projector_matrix = np.eye(3, dtype=np.float32)
    context.app_config.camera_matrix = np.eye(3, dtype=np.float32)
    context.app_config.distortion_coefficients = np.zeros(5, dtype=np.float32)
    context.last_camera_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    context.raw_aruco = {"ids": [], "corners": []}
    return context


@patch("light_map.calibration.calibration_scenes.calibrate_extrinsics")
@patch("os.path.exists")
def test_extrinsics_scene_passes_known_targets(
    mock_exists, mock_calibrate, mock_context
):
    """
    Verifies that the scene correctly maps detected markers to target zones
    and passes these known (tx, ty) coordinates to the calibration logic.
    """
    mock_exists.return_value = False  # No ground points file

    # Mock return for calibrate_extrinsics: (rotation_vector, translation_vector, object_points, image_points)
    mock_calibrate.return_value = (
        np.zeros(3),
        np.zeros(3),
        np.zeros((3, 3)),
        np.zeros((3, 2)),
    )

    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()

    # Target zones are: (220, 180), ...
    # We'll simulate 3 markers near the first 3 targets.
    ids = [10, 11, 12]
    # Corners near TL (220,180), TR (w-220+30, 180-20), BL (220-40, h-180+15)
    corners = [
        np.array(
            [[210, 170], [230, 170], [230, 190], [210, 190]], dtype=np.float32
        ).reshape(1, 4, 2),
        np.array(
            [[1720, 150], [1740, 150], [1740, 170], [1720, 170]], dtype=np.float32
        ).reshape(1, 4, 2),
        np.array(
            [[170, 905], [190, 905], [190, 925], [170, 925]], dtype=np.float32
        ).reshape(1, 4, 2),
    ]
    mock_context.raw_aruco = {"ids": ids, "corners": corners}

    # 1. Update during PLACEMENT to detect markers
    scene.update([], [], 1.0)

    assert scene._target_status[0] == "VALID"
    assert scene._target_status[1] == "VALID"
    assert scene._target_status[2] == "VALID"

    # 2. Trigger Capture with Fist
    inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), (0.0, 0.0), None)]
    scene.update(inputs, [], 1.1)

    # 3. Update again to run CAPTURE logic
    scene.update(inputs, [], 1.2)

    # 4. Verify calibrate_extrinsics call
    assert mock_calibrate.called
    _, kwargs = mock_calibrate.call_args

    known_targets = kwargs.get("known_targets")
    assert known_targets is not None
    assert len(known_targets) == 3

    # Target 0: (220, 180)
    assert known_targets[10] == (220.0, 180.0)
    # Target 1: (1730.0, 160.0)
    assert known_targets[11] == (1730.0, 160.0)
    # Target 2: (180.0, 915.0)
    assert known_targets[12] == (180.0, 915.0)


@patch("cv2.rectangle")
def test_extrinsics_scene_renders_rectangles(mock_rect, mock_context):
    """
    Verifies that the scene renders rectangular target zones via CalibrationLayer.
    """
    from light_map.rendering.layers.calibration_layer import CalibrationLayer
    from light_map.state.world_state import WorldState

    # We need a real WorldState to hold the calibration state
    state = WorldState()
    mock_context.state = state

    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()

    # Simulate some detected markers to change status to VALID
    scene._target_status[0] = "VALID"
    scene._target_info[0] = {
        "x": 220,
        "y": 180,
        "aid": 10,
        "height": 25.0,
        "size": 1,
        "name": "Token 10",
    }
    scene._sync_calibration_state()

    # Create the layer and render
    layer = CalibrationLayer(state, mock_context.app_config)
    layer.render(0.0)

    # PPI is 100, size is 1 -> rect_size = 100, half_size = 50
    # Target 0 is at (220, 180)
    # Expected rect: (170, 130) to (270, 230)

    found_expected = False
    for call in mock_rect.call_args_list:
        args, kwargs = call
        # args[0] is canvas, args[1] is pt1, args[2] is pt2
        if len(args) >= 3:
            pt1, pt2 = args[1], args[2]
            if pt1 == (170, 130) and pt2 == (270, 230):
                found_expected = True
                break

    assert found_expected, "Target rectangle not rendered with correct coordinates"
