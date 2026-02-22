from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.common_types import SceneId, GestureType
from light_map.scenes.calibration_scenes import PpiCalibrationScene
from light_map.core.scene import HandInput, SceneTransition


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    mock_context = MagicMock()
    mock_context.projector_matrix = np.eye(3)
    mock_context.last_camera_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_context.map_config_manager = MagicMock()
    mock_context.notifications = MagicMock()
    return mock_context


def test_ppi_calibration_scene_detecting_to_confirming(mock_app_context):
    """Verify transition from DETECTING to CONFIRMING when PPI is detected."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()

    # Simulate PPI detection
    with patch(
        "light_map.scenes.calibration_scenes.calculate_ppi_from_frame",
        return_value=100.0,
    ) as mock_calc:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        scene.render(frame)  # Call render to trigger detection
        mock_calc.assert_called_with(
            mock_app_context.last_camera_frame,
            mock_app_context.projector_matrix,
            target_dist_mm=100.0,
        )

    assert scene._stage == "CONFIRMING"
    assert scene._candidate_ppi == 100.0


def test_ppi_calibration_scene_confirming_to_done(mock_app_context):
    """Verify transition from CONFIRMING to MENU when VICTORY gesture is detected."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()
    scene._stage = "CONFIRMING"
    scene._candidate_ppi = 120.0

    # Simulate VICTORY gesture
    inputs = [
        HandInput(
            gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=MagicMock()
        )
    ]
    transition = scene.update(inputs, 0.0)

    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU
    mock_app_context.map_config_manager.set_ppi.assert_called_with(120.0)


def test_ppi_calibration_scene_confirming_to_detecting(mock_app_context):
    """Verify transition back to DETECTING when OPEN_PALM gesture is detected."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()
    scene._stage = "CONFIRMING"

    # Simulate OPEN_PALM gesture
    inputs = [
        HandInput(
            gesture=GestureType.OPEN_PALM, proj_pos=(0, 0), raw_landmarks=MagicMock()
        )
    ]
    scene.update(inputs, 0.0)

    assert scene._stage == "DETECTING"


def test_ppi_calibration_scene_no_detection(mock_app_context):
    """Verify no transition if PPI is not detected."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()

    # Simulate no PPI detection
    with patch(
        "light_map.scenes.calibration_scenes.calculate_ppi_from_frame",
        return_value=None,
    ):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        scene.render(frame)  # Call render to trigger detection

    assert scene._stage == "DETECTING"
