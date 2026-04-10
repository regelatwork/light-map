import pytest
from unittest.mock import MagicMock, patch
import numpy as np
import os

from light_map.core.app_context import AppContext
from light_map.calibration.calibration_scenes import (
    MapGridCalibrationScene,
    GridOverlay,
)
from light_map.core.common_types import AppConfig, GestureType, SceneId
from light_map.core.scene import HandInput, SceneTransition
from light_map.map.map_system import MapSystem, MapState
from light_map.map.map_config import MapEntry


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1000, height=1000, projector_matrix=np.eye(3))
    mock_context = MagicMock(spec=AppContext)
    mock_context.app_config = app_config
    mock_context.projector_matrix = np.eye(3)

    # Mock MapSystem and its internal state
    mock_map_system = MagicMock(spec=MapSystem)
    mock_map_system.state = MapState(x=0.0, y=0.0, zoom=1.0, rotation=0.0)
    mock_map_system.base_scale = 1.0
    mock_map_system.svg_loader = MagicMock()
    mock_map_system.svg_loader.filename = "test_map.svg"
    # Mock coordinate transforms
    mock_map_system.screen_to_world.side_effect = lambda sx, sy: (
        sx / 2.0,
        sy / 2.0,
    )  # Assume zoom=2 for easy math
    mock_map_system.state.zoom = 2.0

    mock_context.map_system = mock_map_system

    # Mock MapConfigManager
    mock_map_config_manager = MagicMock()
    mock_map_config_manager.get_ppi.return_value = 100.0
    mock_map_config_manager.data = MagicMock()
    mock_map_config_manager.data.maps = {}
    mock_context.map_config_manager = mock_map_config_manager

    mock_context.notifications = MagicMock()
    mock_context.events = MagicMock()
    mock_context.analytics = MagicMock()
    return mock_context


@pytest.fixture
def map_grid_calib_scene(mock_app_context):
    return MapGridCalibrationScene(mock_app_context)


def test_map_grid_calibration_on_enter_initializes_overlay(
    map_grid_calib_scene, mock_app_context
):
    """Verify on_enter initializes GridOverlay centered on screen."""
    map_grid_calib_scene.on_enter()

    assert map_grid_calib_scene.grid_overlay is not None
    assert isinstance(map_grid_calib_scene.grid_overlay, GridOverlay)
    # Spacing should be PPI * 1.0 = 100.0
    assert map_grid_calib_scene.grid_overlay.spacing == 100.0

    # Verify centering (screen is 1000x1000)
    assert map_grid_calib_scene.grid_overlay.offset_x == 500.0
    assert map_grid_calib_scene.grid_overlay.offset_y == 500.0

    # Ensure map view was NOT reset
    mock_app_context.map_system.reset_view_to_base.assert_not_called()


def test_map_grid_calibration_on_enter_restores_from_config(
    map_grid_calib_scene, mock_app_context
):
    """Verify on_enter restores grid from existing config aligned to viewport."""
    # Setup existing config
    abs_path = os.path.abspath("test_map.svg")
    # Mocking map_config_manager.data.maps
    mock_app_context.map_config_manager.data = MagicMock()
    mock_app_context.map_config_manager.data.maps = {
        abs_path: MapEntry(
            grid_spacing_svg=50.0, grid_origin_svg_x=100.0, grid_origin_svg_y=100.0
        )
    }

    # Setup viewport (zoom=2.0 already set in fixture)
    mock_app_context.map_system.world_to_screen.return_value = (250.0, 350.0)

    map_grid_calib_scene.on_enter()

    # Expected screen spacing: svg_spacing (50) * zoom (2.0) = 100.0
    assert map_grid_calib_scene.grid_overlay.spacing == 100.0
    # Expected screen offset: world_to_screen(100, 100) = (250.0, 350.0)
    assert map_grid_calib_scene.grid_overlay.offset_x == 250.0
    assert map_grid_calib_scene.grid_overlay.offset_y == 350.0


@patch("time.monotonic")
def test_map_grid_calibration_confirm_saves_config(
    mock_monotonic, map_grid_calib_scene, mock_app_context
):
    """Verify that holding VICTORY gesture saves calibration derived from overlay."""
    mock_monotonic.side_effect = [0.1, 1.11]
    map_grid_calib_scene.on_enter()

    # Manipulate overlay state
    overlay = map_grid_calib_scene.grid_overlay
    overlay.spacing = 200.0
    overlay.offset_x = 50.0
    overlay.offset_y = 60.0

    inputs = [
        HandInput(
            gesture=GestureType.VICTORY,
            proj_pos=(0, 0),
            unit_direction=(0.0, 0.0),
            raw_landmarks=None,
        )
    ]

    # First call - should trigger schedule
    mock_app_context.events.has_event.return_value = False
    map_grid_calib_scene.update(inputs, [], mock_monotonic())

    # Check if schedule was called.
    mock_app_context.events.schedule.assert_called()

    # Manually trigger the callback
    map_grid_calib_scene._on_save_triggered()

    # Now the next update should return the transition
    transition = map_grid_calib_scene.update(inputs, [], mock_monotonic())

    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MENU

    # Expected calculations:
    # derived_spacing = overlay.spacing / map_zoom = 200.0 / 2.0 = 100.0
    # origin = screen_to_world(50, 60) -> (25.0, 30.0) from our mock lambda

    # Derived base scale = (1.0 * 100 PPI) / 100.0 spacing = 1.0

    mock_app_context.map_config_manager.save_map_grid_config.assert_called_with(
        "test_map.svg",
        grid_spacing_svg=100.0,
        grid_origin_svg_x=25.0,
        grid_origin_svg_y=30.0,
        physical_unit_inches=1.0,
        scale_factor_1to1=1.0,
    )


def test_map_grid_calibration_interaction_updates_overlay(
    map_grid_calib_scene, mock_app_context
):
    """Verify that interactions are directed to the GridOverlay."""
    map_grid_calib_scene.on_enter()

    with patch.object(
        map_grid_calib_scene.interaction_controller, "process_gestures"
    ) as mock_process:
        inputs = [
            HandInput(
                gesture=GestureType.POINTING,
                proj_pos=(100, 100),
                unit_direction=(0.0, 0.0),
                raw_landmarks=None,
            )
        ]
        map_grid_calib_scene.update(inputs, [], 0.0)

        # Should call process_gestures with the grid_overlay as target
        mock_process.assert_called_once_with(inputs, map_grid_calib_scene.grid_overlay)


def test_grid_overlay_logic():
    """Verify GridOverlay pan and zoom logic (Anchor and Scale)."""
    mock_config = MagicMock(spec=AppConfig)
    mock_config.width = 500
    mock_config.height = 500
    overlay = GridOverlay(start_spacing=100.0, config=mock_config)

    # Test Pan
    overlay.pan(10, 20)
    assert overlay.offset_x == 10.0
    assert overlay.offset_y == 20.0

    # Test Zoom Pinned (New Behavior: Pivots around offset)
    # Zoom x2 around arbitrary point (100, 100)
    # Should ignore center point and keep offset fixed
    overlay.zoom_pinned(2.0, (100, 100))

    assert overlay.spacing == 200.0
    # Offsets should NOT change
    assert overlay.offset_x == 10.0
    assert overlay.offset_y == 20.0


def test_map_grid_calibration_render(map_grid_calib_scene, mock_app_context):
    """Verify render draws crosses and highlighted origin."""
    map_grid_calib_scene.on_enter()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Configure overlay to draw one intersection at (50, 50)
    map_grid_calib_scene.grid_overlay.spacing = 100.0
    map_grid_calib_scene.grid_overlay.offset_x = 50.0
    map_grid_calib_scene.grid_overlay.offset_y = 50.0
    # Width and height are now properties fetching from context.app_config
    mock_app_context.app_config.width = 100
    mock_app_context.app_config.height = 100

    with patch("cv2.line") as mock_line, patch("cv2.circle") as mock_circle:
        map_grid_calib_scene.render(frame)

        # Verify crosses (lines)
        assert mock_line.call_count >= 4

        # Verify Origin Highlight (Green Circle)
        green_circle_found = False
        for call in mock_circle.call_args_list:
            args, _ = call
            # args[3] is color in cv2.circle(img, center, radius, color, thickness)
            if args[3] == (0, 255, 0):
                green_circle_found = True
        assert green_circle_found, "Green highlight circle not found"
