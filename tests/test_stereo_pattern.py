import cv2
import numpy as np

from light_map.calibration.calibration_scenes import StereoCalibrationScene, StereoCalibStage
from light_map.core.common_types import AppConfig, CalibrationState
from light_map.rendering.layers.calibration_layer import CalibrationLayer
from light_map.rendering.stereo_pattern import generate_stereo_calibration_pattern
from light_map.state.world_state import WorldState


def test_generate_stereo_calibration_pattern_dimensions_and_metadata():
    """Verify generate_stereo_calibration_pattern returns an image of exact dimensions and metadata."""
    width, height, ppi = 1920, 1080, 96.0
    img, params = generate_stereo_calibration_pattern(width, height, ppi=ppi)

    assert img is not None
    assert img.shape == (height, width, 3)
    assert img.dtype == np.uint8

    # Verify grid markers
    grid_markers = params["grid_markers"]
    assert len(grid_markers) == 8
    grid_ids = [m["id"] for m in grid_markers]
    assert grid_ids == list(range(42, 50))

    # Verify ruler targets (IDs 40 & 41)
    ruler = params["ruler_targets"]
    assert ruler["distance_mm"] == 100.0
    assert "m40" in ruler
    assert "m41" in ruler
    # Distance between m40 and m41 in pixels should match 100mm * ppi / 25.4
    expected_dist_px = 100.0 * ppi / 25.4
    actual_dist_px = np.linalg.norm(np.array(ruler["m40"]) - np.array(ruler["m41"]))
    assert np.isclose(actual_dist_px, expected_dist_px, atol=2.0)

    # Verify 4 corner tokens (0-3: Cricket, Lace, Shikra, Verita)
    tokens = params["token_targets"]
    assert len(tokens) == 4
    token_ids = [t["id"] for t in tokens]
    assert token_ids == [0, 1, 2, 3]
    token_names = [t["name"] for t in tokens]
    assert token_names == ["Cricket", "Lace", "Shikra", "Verita"]
    for t in tokens:
        assert t["height_mm"] == 50.0
        assert t["shape"] == "square"
        assert t["size_px"] >= 24

    # Verify targets span across the display (at least 70% width and height coverage)
    xs = [t["x"] for t in tokens]
    ys = [t["y"] for t in tokens]
    width_coverage = (max(xs) - min(xs)) / width
    height_coverage = (max(ys) - min(ys)) / height
    assert width_coverage >= 0.70, f"Width coverage {width_coverage:.2f} too low"
    assert height_coverage >= 0.65, f"Height coverage {height_coverage:.2f} too low"


def test_generate_stereo_calibration_pattern_optical_markers_detectable():
    """Verify that OpenCV's ArUco detector detects the 8 projected markers (42-49)."""
    width, height, ppi = 1920, 1080, 96.0
    img, _ = generate_stereo_calibration_pattern(width, height, ppi=ppi)

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    corners, ids, _ = detector.detectMarkers(img)
    assert ids is not None
    detected_ids = [int(i[0]) for i in ids]
    for expected_id in range(42, 50):
        assert expected_id in detected_ids, f"Projected marker {expected_id} not detected"


def test_calibration_layer_renders_target_squares():
    """Verify CalibrationLayer renders target squares when shape is square."""
    config = AppConfig(width=800, height=600, projector_matrix=np.eye(3), projector_ppi=96.0)
    state = WorldState()
    layer = CalibrationLayer(state, config, render_instructions=False)

    state.calibration = CalibrationState(
        stage="ALIGNMENT",
        target_info=[
            {
                "x": 200,
                "y": 200,
                "name": "Cricket",
                "height": 50.0,
                "aid": 0,
                "size": 1,
                "shape": "square",
                "size_px": 40,
            }
        ],
        target_status=["VALID"],
    )

    patches = layer._generate_patches(0.0)
    assert len(patches) == 1
    canvas = patches[0].data
    assert canvas.shape == (600, 800, 4)
    center_pixel = canvas[200, 200]
    assert center_pixel[3] == 255  # Alpha channel is solid
    # When VALID, center area should be illuminated green
    assert canvas[200, 200][1] > 180  # Green channel active


def test_calibration_layer_preserves_idle_pattern_squares():
    """Verify CalibrationLayer does not overwrite pattern squares in pure white during IDLE."""
    config = AppConfig(width=800, height=600, projector_matrix=np.eye(3), projector_ppi=96.0)
    state = WorldState()
    layer = CalibrationLayer(state, config, render_instructions=False)

    base_img = np.full((600, 800, 3), 255, dtype=np.uint8)
    # Draw a non-white square on base_img
    cv2.rectangle(base_img, (180, 180), (220, 220), (180, 40, 10), 3)

    state.calibration = CalibrationState(
        stage="ALIGNMENT",
        pattern_image=base_img,
        target_info=[
            {
                "x": 200,
                "y": 200,
                "name": "Cricket",
                "height": 50.0,
                "aid": 0,
                "size": 1,
                "shape": "square",
                "size_px": 40,
            }
        ],
        target_status=["IDLE"],
    )

    patches = layer._generate_patches(0.0)
    canvas = patches[0].data
    # Check pixel on the square edge (220, 200)
    edge_pixel = canvas[200, 220]
    # Square edge pixel should NOT be white [255, 255, 255, 255]
    assert not np.array_equal(edge_pixel[:3], [255, 255, 255])
    assert np.array_equal(edge_pixel[:3], [180, 40, 10])


def test_stereo_calibration_scene_populates_pattern_and_targets():
    """Verify StereoCalibrationScene populates pattern_image and target_info on enter."""
    from unittest.mock import MagicMock

    mock_context = MagicMock()
    mock_context.app_config = AppConfig(
        width=1920, height=1080, projector_matrix=np.eye(3), projector_ppi=96.0
    )
    mock_context.state = WorldState()

    scene = StereoCalibrationScene(mock_context)
    scene.on_enter()

    assert scene.stage == StereoCalibStage.ALIGNMENT
    cal = mock_context.state.calibration
    assert cal is not None
    assert cal.pattern_image is not None
    assert cal.pattern_image.shape == (1080, 1920, 3)
    assert len(cal.target_info) == 4
    assert [t["aid"] for t in cal.target_info] == [0, 1, 2, 3]
    assert all(t["shape"] == "square" for t in cal.target_info)
    assert cal.target_status == ["IDLE", "IDLE", "IDLE", "IDLE"]


def test_stereo_calibration_scene_updates_target_status_on_detection():
    """Verify StereoCalibrationScene marks targets VALID when detected in raw_aruco."""
    from unittest.mock import MagicMock

    mock_context = MagicMock()
    mock_context.app_config = AppConfig(
        width=1920, height=1080, projector_matrix=np.eye(3), projector_ppi=96.0
    )
    mock_context.state = WorldState()
    mock_context.raw_aruco = {"ids": [0, 2], "corners": []}

    scene = StereoCalibrationScene(mock_context)
    scene.on_enter()

    scene.update(inputs=[], actions=[], current_time=1.0)
    cal = mock_context.state.calibration
    assert cal.target_status[0] == "VALID"
    assert cal.target_status[1] == "IDLE"
    assert cal.target_status[2] == "VALID"
    assert cal.target_status[3] == "IDLE"


def test_stereo_calibration_scene_victory_gesture_triggers_solve():
    """Verify holding Victory gesture in ALIGNMENT schedules solve and transitions stage."""
    from unittest.mock import MagicMock

    from light_map.core.common_types import GestureType, TimerKey
    from light_map.core.scene import HandInput

    mock_context = MagicMock()
    mock_context.app_config = AppConfig(
        width=1920, height=1080, projector_matrix=np.eye(3), projector_ppi=96.0
    )
    mock_context.state = WorldState()
    mock_context.events.has_event.return_value = False

    scene = StereoCalibrationScene(mock_context)
    scene.on_enter()

    hand_input = HandInput(
        gesture=GestureType.VICTORY,
        proj_pos=(100, 100),
        unit_direction=(0.0, 1.0),
        raw_landmarks=None,
    )
    scene.update(inputs=[hand_input], actions=[], current_time=1.0)

    # Verify 1.0s timer was scheduled with CALIBRATION_STAGE key
    mock_context.events.schedule.assert_called_once()
    args, kwargs = mock_context.events.schedule.call_args
    assert args[0] == 1.0
    assert kwargs["key"] == TimerKey.CALIBRATION_STAGE

    # Trigger callback
    callback = args[1]
    callback()
    assert scene.stage in (StereoCalibStage.SOLVING, StereoCalibStage.VALIDATION)
