import pytest
import numpy as np
from typing import List
from unittest.mock import MagicMock, patch
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.common_types import GestureType, AppMode, MenuActions
from light_map.menu_config import ROOT_MENU


# Mock MediaPipe Results
class MockHandLandmark:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z


class MockResults:
    def __init__(
        self,
        hands_landmarks: List[List[MockHandLandmark]] = None,
        labels: List[str] = None,
    ):
        if hands_landmarks:
            self.multi_hand_landmarks = [
                MagicMock(landmark=lm) for lm in hands_landmarks
            ]
            self.multi_handedness = []
            for label in labels or ["Right"] * len(hands_landmarks):
                classification = MagicMock()
                classification.label = label
                self.multi_handedness.append(MagicMock(classification=[classification]))
        else:
            self.multi_hand_landmarks = None
            self.multi_handedness = None


@pytest.fixture
def app_config():
    matrix = np.eye(3, dtype=np.float32)
    return AppConfig(
        width=100, height=100, projector_matrix=matrix, root_menu=ROOT_MENU
    )


def test_interactive_app_initialization(app_config):
    app = InteractiveApp(app_config)
    assert app is not None
    assert app.menu_system is not None
    assert app.mode == AppMode.MENU


def test_process_frame_no_hands(app_config):
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults(hands_landmarks=None)
    output, actions = app.process_frame(frame, results)
    assert output.shape == (100, 100, 3)


def test_mode_switch_to_map(app_config):
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Mock MenuSystem to return MAP_CONTROLS action
    with patch.object(app.menu_system, "update") as mock_update:
        mock_state = MagicMock()
        mock_state.just_triggered_action = MenuActions.MAP_CONTROLS
        mock_state.is_visible = True
        mock_update.return_value = mock_state

        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])
        app.process_frame(frame, results)

        assert app.mode == AppMode.MAP


def test_panning_in_map_mode(app_config):

    app = InteractiveApp(app_config)

    app.mode = AppMode.MAP

    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        # Panning now uses CLOSED_FIST
        mock_detect.return_value = GestureType.CLOSED_FIST

        # Frame 1: Initial position

        results1 = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])

        app.process_frame(frame, results1)

        # Frame 2: Move hand right (0.5 -> 0.6)

        # In 100x100, this is 50 -> 60. dx = 10.

        results2 = MockResults(hands_landmarks=[[MockHandLandmark(0.6, 0.5)] * 21])

        app.process_frame(frame, results2)

        assert app.map_system.state.x == 10.0


def test_zooming_in_map_mode(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.MAP
    app.time_provider = MagicMock(return_value=0.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.POINTING

        # Frame 1: Hands at 40 and 60 (dist 20)
        h1 = [MockHandLandmark(0.4, 0.5)] * 21
        h2 = [MockHandLandmark(0.6, 0.5)] * 21
        results1 = MockResults(hands_landmarks=[h1, h2])

        # Initial call to start timer
        app.time_provider.return_value = 1.0
        app.process_frame(frame, results1)

        # Second call after delay (e.g. 1.6s > 0.5s)
        app.time_provider.return_value = 2.0
        app.process_frame(frame, results1)

        # Hands now at 30 and 70 (dist 40)
        # Scale factor = 40/20 = 2.0
        h1_new = [MockHandLandmark(0.3, 0.5)] * 21
        h2_new = [MockHandLandmark(0.7, 0.5)] * 21
        results2 = MockResults(hands_landmarks=[h1_new, h2_new])

        app.process_frame(frame, results2)

        # Initial zoom was 1.0, so new zoom should be 2.0
        assert app.map_system.state.zoom == 2.0
        
        # Fixed Pivot at Screen Center (50, 50)
        # 50 = 50 * 2.0 + PanX => PanX = -50
        assert app.map_system.state.x == -50.0
        assert app.map_system.state.y == -50.0


def test_exit_map_mode(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.MAP
    app.time_provider = MagicMock(return_value=0.0)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.VICTORY
        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])

        # Frame 1: Starts timer
        app.time_provider.return_value = 1.0
        app.process_frame(frame, results)
        assert app.mode == AppMode.MAP

        # Frame 2: 0.5s later (Not enough)
        app.time_provider.return_value = 1.5
        app.process_frame(frame, results)
        assert app.mode == AppMode.MAP

        # Frame 3: 1.1s later (Enough)
        app.time_provider.return_value = 2.2
        app.process_frame(frame, results)
        assert app.mode == AppMode.MENU


def test_ppi_calibration_flow(app_config):
    app = InteractiveApp(app_config)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # 1. Enter Calibration Mode
    app.mode = AppMode.CALIB_PPI
    app.calib_stage = 0

    # 2. Simulate detection
    with patch("light_map.interactive_app.calculate_ppi_from_frame") as mock_calc:
        mock_calc.return_value = 120.0

        results = MockResults(hands_landmarks=None)
        app.process_frame(frame, results)

        assert app.calib_stage == 1
        assert app.calib_candidate_ppi == 120.0

    # 3. Confirm with Gesture
    with patch("light_map.interactive_app.detect_gesture") as mock_detect:
        mock_detect.return_value = GestureType.VICTORY
        results = MockResults(hands_landmarks=[[MockHandLandmark(0.5, 0.5)] * 21])

        with patch.object(app.map_config, "set_ppi") as mock_save:
            app.process_frame(frame, results)

            mock_save.assert_called_with(120.0)
            assert app.mode == AppMode.MENU


def test_process_frame_renders_map_in_menu_mode(app_config):
    app = InteractiveApp(app_config)
    app.mode = AppMode.MENU  # Default
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    results = MockResults(hands_landmarks=None)

    # Mock SVGLoader
    with patch("light_map.interactive_app.SVGLoader") as MockLoader:
        loader_instance = MagicMock()
        MockLoader.return_value = loader_instance

        # Make render return a green image
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        bg[:, :] = (0, 255, 0)
        loader_instance.render.return_value = bg
        loader_instance.detect_grid_spacing.return_value = 50.0

        app.load_map("dummy.svg")
        output, actions = app.process_frame(frame, results)

        # Verify loader was called even in MENU mode
        loader_instance.render.assert_called_once()

        # Verify output contains green
        assert np.array_equal(output[50, 50], [0, 255, 0])
