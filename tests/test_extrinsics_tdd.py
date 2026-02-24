import pytest
import numpy as np
import math
from unittest.mock import MagicMock, patch
from light_map.scenes.calibration_scenes import ExtrinsicsCalibrationScene
from light_map.core.scene import HandInput
from light_map.gestures import GestureType

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.app_config.width = 1920
    context.app_config.height = 1080
    context.map_config_manager.get_ppi.return_value = 100.0  # Use 100 PPI for easy math
    
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
        mock_token.size = 1 # 1x1 inch
        return mock_token
        
    context.map_config_manager.resolve_token_profile.side_effect = mock_resolve
    context.projector_matrix = np.eye(3)
    context.camera_matrix = np.eye(3)
    context.dist_coeffs = np.zeros(5)
    context.last_camera_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    return context

@patch("light_map.scenes.calibration_scenes.calibrate_extrinsics")
@patch("os.path.exists")
def test_extrinsics_scene_passes_known_targets(mock_exists, mock_calibrate, mock_context):
    """
    Verifies that the scene correctly maps detected markers to target zones
    and passes these known (tx, ty) coordinates to the calibration logic.
    """
    mock_exists.return_value = False # No ground points file
    
    # Mock return for calibrate_extrinsics: (rvec, tvec, obj_points, img_points)
    mock_calibrate.return_value = (np.zeros(3), np.zeros(3), np.zeros((3, 3)), np.zeros((3, 2)))
    
    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()
    
    # Target zones are: (200, 200), (1720, 200), (200, 880), (1720, 880), (960, 540)
    # We'll simulate 3 markers near the first 3 targets.
    
    with (
        patch("cv2.aruco.ArucoDetector") as MockDetector,
        patch("cv2.aruco.getPredefinedDictionary"),
        patch("cv2.aruco.DetectorParameters"),
    ):
        
        detector_instance = MockDetector.return_value
        ids = np.array([[10], [11], [12]], dtype=np.int32)
        # Corners near TL (200,200), TR (1720,200), BL (200,880)
        # Note: In world coordinates (identity projector matrix), camera (u,v) = projector (x,y)
        corners = (
            np.array([[[190, 190], [210, 190], [210, 210], [190, 210]]], dtype=np.float32),
            np.array([[[1710, 190], [1730, 190], [1730, 210], [1710, 210]]], dtype=np.float32),
            np.array([[[190, 870], [210, 870], [210, 890], [190, 890]]], dtype=np.float32),
        )
        detector_instance.detectMarkers.return_value = (corners, ids, [])
        
        # 1. Update during PLACEMENT to detect markers
        scene.update([], 1.0)
        
        assert scene._target_status[0] == "VALID"
        assert scene._target_status[1] == "VALID"
        assert scene._target_status[2] == "VALID"
        
        # 2. Trigger Capture with Fist
        inputs = [HandInput(GestureType.CLOSED_FIST, (0, 0), None)]
        scene.update(inputs, 1.1)
        
        # 3. Update again to run CAPTURE logic
        scene.update(inputs, 1.2)
        
        # 4. Verify calibrate_extrinsics call
        assert mock_calibrate.called
        _, kwargs = mock_calibrate.call_args
        
        known_targets = kwargs.get("known_targets")
        assert known_targets is not None
        assert len(known_targets) == 3
        
        # Target 0: (200, 200)
        assert known_targets[10] == (200.0, 200.0)
        # Target 1: (1720, 200)
        assert known_targets[11] == (1720.0, 200.0)
        # Target 2: (200, 880)
        assert known_targets[12] == (200.0, 880.0)

@patch("cv2.rectangle")
def test_extrinsics_scene_renders_rectangles(mock_rect, mock_context):
    """
    Verifies that the scene renders rectangular target zones.
    """
    scene = ExtrinsicsCalibrationScene(mock_context)
    scene.on_enter()
    
    # Simulate some detected markers to change status to VALID
    scene._target_status[0] = "VALID"
    scene._target_info[0] = {"aid": 10, "height": 25.0, "size": 1, "name": "Token 10"}
    
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    scene.render(frame)
    
    # PPI is 100, size is 1 -> rect_size = 100, half_size = 50
    # Target 0 is at (200, 200)
    # Expected rect: (200-50, 200-50) to (200+50, 200+50) -> (150, 150) to (250, 250)
    
    # Check if any call to cv2.rectangle matches the expected coordinates
    found_expected = False
    for call in mock_rect.call_args_list:
        args, kwargs = call
        # args[1] is pt1, args[2] is pt2
        pt1, pt2 = args[1], args[2]
        if pt1 == (150, 150) and pt2 == (250, 250):
            found_expected = True
            break
            
    assert found_expected, "Target rectangle not rendered with correct coordinates"
