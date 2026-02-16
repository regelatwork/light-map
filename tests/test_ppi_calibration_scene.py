import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from light_map.core.app_context import AppContext
from light_map.scenes.calibration_scenes import PpiCalibrationScene
from light_map.common_types import AppConfig, GestureType, SceneId
from light_map.core.scene import HandInput, SceneTransition


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)
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
    ):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        scene.render(frame)  # Call render to trigger detection

    assert scene._stage == "CONFIRMING"
    assert scene._candidate_ppi == 100.0


def test_ppi_calibration_scene_confirm_with_victory(mock_app_context):
    """Verify confirming PPI with VICTORY gesture transitions to MenuScene."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()
    scene._stage = "CONFIRMING"
    scene._candidate_ppi = 100.0

    inputs = [
        HandInput(gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=None)
    ]
    transition = scene.update(inputs, 0.0) # Time doesn't matter here

    mock_app_context.map_config_manager.set_ppi.assert_called_once_with(100.0)
    mock_app_context.notifications.add_notification.assert_called_once_with(
        "PPI saved: 100.00"
    )
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU


def test_ppi_calibration_scene_retry_with_open_palm(mock_app_context):
    """Verify retrying PPI detection with OPEN_PALM gesture resets stage."""
    scene = PpiCalibrationScene(mock_app_context)
    scene.on_enter()
    scene._stage = "CONFIRMING"
    scene._candidate_ppi = 100.0

    inputs = [
        HandInput(gesture=GestureType.OPEN_PALM, proj_pos=(0, 0), raw_landmarks=None)
    ]
    transition = scene.update(inputs, 0.0)

    assert scene._stage == "DETECTING"
    assert transition is None
    mock_app_context.map_config_manager.set_ppi.assert_not_called()
    mock_app_context.notifications.add_notification.assert_not_called()


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

    assert scene._stage == "DETECTING"  # Should remain in DETECTING
    assert scene._candidate_ppi == 0.0
