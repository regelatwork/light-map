import pytest
from unittest.mock import MagicMock, patch
import numpy as np
import copy

from light_map.core.app_context import AppContext
from light_map.scenes.calibration_scenes import MapGridCalibrationScene
from light_map.common_types import AppConfig, GestureType, SceneId
from light_map.core.scene import HandInput, SceneTransition
from light_map.map_system import MapSystem, MapState


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)

    # Mock MapSystem and its internal state
    mock_map_system = MagicMock(spec=MapSystem)
    mock_map_system.state = MapState(x=0.0, y=0.0, zoom=1.0, rotation=0.0)
    mock_map_system.base_scale = 1.0
    mock_map_system.svg_loader = MagicMock()
    mock_map_system.svg_loader.filename = "test_map.svg"
    mock_context.map_system = mock_map_system

    # Mock MapConfigManager
    mock_map_config_manager = MagicMock()
    mock_map_config_manager.get_ppi.return_value = 96.0
    mock_context.map_config_manager = mock_map_config_manager

    mock_context.notifications = MagicMock()
    return mock_context


@pytest.fixture
def map_grid_calib_scene(mock_app_context):
    return MapGridCalibrationScene(mock_app_context)


def test_map_grid_calibration_on_enter_resets_view_and_saves_state(
    map_grid_calib_scene, mock_app_context
):
    """Verify on_enter saves current map state and resets view for calibration."""
    # Set an initial state for MapSystem
    mock_app_context.map_system.state.x = 100
    mock_app_context.map_system.state.y = 50
    mock_app_context.map_system.state.zoom = 2.0
    mock_app_context.map_system.state.rotation = 90.0
    mock_app_context.map_system.base_scale = 1.5 # Should use this for reset

    map_grid_calib_scene.on_enter()

    # Verify current map state was saved
    assert isinstance(map_grid_calib_scene._saved_map_state, MapState)
    assert map_grid_calib_scene._saved_map_state.x == 100
    assert map_grid_calib_scene._saved_map_state.zoom == 2.0

    # Verify map system was reset to base view
    mock_app_context.map_system.reset_view_to_base.assert_called_once()


def test_map_grid_calibration_on_exit_restores_view(map_grid_calib_scene, mock_app_context):
    """Verify on_exit restores the saved map state if calibration was not confirmed."""
    # Simulate a saved state (e.g., from on_enter)
    saved_state = MapState(x=100, y=50, zoom=2.0, rotation=90.0)
    map_grid_calib_scene._saved_map_state = saved_state

    map_grid_calib_scene.on_exit()

    # Verify map system state was restored
    assert mock_app_context.map_system.state == saved_state
    assert map_grid_calib_scene._saved_map_state is None # Should be cleared after restore


def test_map_grid_calibration_on_exit_does_not_restore_if_saved(
    map_grid_calib_scene, mock_app_context
):
    """Verify on_exit does NOT restore if _saved_map_state was cleared (e.g., calibration confirmed)."""
    # Simulate state where calibration was confirmed and _saved_map_state was cleared
    map_grid_calib_scene._saved_map_state = None
    initial_map_state = copy.deepcopy(mock_app_context.map_system.state)

    map_grid_calib_scene.on_exit()

    # Verify map system state remains unchanged
    assert mock_app_context.map_system.state == initial_map_state
    mock_app_context.map_system.set_state.assert_not_called()


@patch("time.monotonic")
def test_map_grid_calibration_confirm_saves_config_and_transitions(
    mock_monotonic, map_grid_calib_scene, mock_app_context
):
    """Verify that holding VICTORY gesture saves calibration and transitions to MenuScene."""
    mock_monotonic.side_effect = [0.1, 1.11]

    # Setup initial state for calibration
    map_grid_calib_scene.on_enter() # Does not consume mock_monotonic
    mock_app_context.map_system.state.zoom = 1.25  # Calibrated zoom
    mock_app_context.map_config_manager.get_ppi.return_value = 100.0

    inputs = [
        HandInput(gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=None)
    ]

    # First call to update: simulate start of gesture, sets summon_gesture_start_time
    map_grid_calib_scene.update(inputs, mock_monotonic())

    # Second call to update: simulate holding gesture, triggers transition
    transition = map_grid_calib_scene.update(inputs, mock_monotonic())

    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU

    mock_app_context.map_config_manager.save_map_grid_config.assert_called_once_with(
        "test_map.svg",
        grid_spacing_svg=80.0,  # 100 PPI * 1.0 inch / 1.25 zoom = 80.0
        grid_origin_svg_x=0.0,
        grid_origin_svg_y=0.0,
        physical_unit_inches=1.0,
        scale_factor_1to1=1.25,
    )
    assert mock_app_context.map_system.base_scale == 1.25
    mock_app_context.notifications.add_notification.assert_called_once_with(
        "Map grid calibrated."
    )
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU


@patch("time.monotonic")
def test_map_grid_calibration_confirm_requires_hold(
    mock_monotonic, map_grid_calib_scene, mock_app_context
):
    """Verify that VICTORY gesture requires a hold to confirm calibration."""
    map_grid_calib_scene.on_enter()

    inputs = [
        HandInput(gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=None)
    ]

    # Simulate short hold (< 1 second)
    # First call is from on_enter, second from update
    mock_monotonic.side_effect = [0.0, 0.5]
    transition = map_grid_calib_scene.update(inputs, mock_monotonic()) # Call mock to get 0.5

    assert transition is None
    mock_app_context.map_config_manager.save_map_grid_config.assert_not_called()


def test_map_grid_calibration_pan_zoom_interaction(map_grid_calib_scene, mock_app_context):
    """Verify that pan/zoom interactions are processed by the interaction controller."""
    map_grid_calib_scene.on_enter()

    with patch.object(map_grid_calib_scene.interaction_controller, "process_gestures") as mock_process_gestures:
        inputs = [
            HandInput(gesture=GestureType.OPEN_PALM, proj_pos=(10, 10), raw_landmarks=None)
        ]
        map_grid_calib_scene.update(inputs, 0.0)

        mock_process_gestures.assert_called_once_with(inputs, mock_app_context.map_system)
        assert map_grid_calib_scene.is_interacting == mock_process_gestures.return_value


@patch("time.monotonic")
def test_map_grid_calibration_no_map_loaded_error(
    mock_monotonic, map_grid_calib_scene, mock_app_context
):
    """Verify that saving calibration without a loaded map shows a notification."""
    mock_monotonic.side_effect = [0.1, 1.11]
    map_grid_calib_scene.on_enter() # Does not consume mock_monotonic
    mock_app_context.map_system.svg_loader = None  # No map loaded

    inputs = [
        HandInput(gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=None)
    ]

    map_grid_calib_scene.update(inputs, mock_monotonic()) # First call sets summon_gesture_start_time = 0.1
    transition = map_grid_calib_scene.update(inputs, mock_monotonic()) # Second call with advanced time

    # The update method should still return a transition to MENU, but _save_calibration
    # will handle the error internally and add a notification.
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU

    mock_app_context.notifications.add_notification.assert_called_once_with(
        "Error: No map loaded for calibration."
    )
    mock_app_context.map_config_manager.save_map_grid_config.assert_not_called()


@patch("time.monotonic")
def test_map_grid_calibration_no_ppi_error(mock_monotonic, map_grid_calib_scene, mock_app_context):
    """Verify that saving calibration without PPI set shows a notification."""
    mock_monotonic.side_effect = [0.1, 1.11]
    map_grid_calib_scene.on_enter() # Does not consume mock_monotonic
    mock_app_context.map_config_manager.get_ppi.return_value = 0.0  # PPI not set

    inputs = [
        HandInput(gesture=GestureType.VICTORY, proj_pos=(0, 0), raw_landmarks=None)
    ]

    map_grid_calib_scene.update(inputs, mock_monotonic()) # First call sets summon_gesture_start_time = 0.1
    transition = map_grid_calib_scene.update(inputs, mock_monotonic()) # Second call with advanced time

    # The update method should still return a transition to MENU, but _save_calibration
    # will handle the error internally and add a notification.
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU

    mock_app_context.notifications.add_notification.assert_called_once_with(
        "Cannot calibrate grid: PPI is not set."
    )
    mock_app_context.map_config_manager.save_map_grid_config.assert_not_called()
