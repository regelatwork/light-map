from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from light_map.common_types import AppConfig, GestureType, MenuActions, SceneId
from light_map.core.app_context import AppContext
from light_map.core.notification import NotificationManager
from light_map.core.scene import HandInput, Scene, SceneTransition
from light_map.input_manager import InputManager
from light_map.map_config import MapConfigManager
from light_map.map_system import MapSystem
from light_map.menu_builder import build_root_menu
from light_map.menu_system import MenuState, MenuSystem, MenuSystemState
from light_map.renderer import Renderer
from light_map.scenes.menu_scene import MenuScene

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext


@pytest.fixture
def mock_app_context():
    """Creates a mock AppContext for testing."""
    app_config = AppConfig(width=1920, height=1080, projector_matrix=np.eye(3))

    # Configure the mock MapConfigManager
    mock_map_config = MagicMock(spec=MapConfigManager)
    mock_map_config.data = MagicMock()
    mock_map_config.data.maps = {}

    mock_context = AppContext(
        app_config=app_config,
        renderer=MagicMock(spec=Renderer),
        map_system=MagicMock(spec=MapSystem),
        map_config_manager=mock_map_config,
        projector_matrix=np.eye(3),
        notifications=MagicMock(spec=NotificationManager),
    )
    # Mock the return value for is_map_loaded
    mock_context.map_system.is_map_loaded.return_value = True
    return mock_context


def test_menu_scene_handles_load_map_action(mock_app_context):
    """Verify that a LOAD_MAP action string creates the correct SceneTransition."""
    # Arrange
    scene = MenuScene(mock_app_context)
    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action="LOAD_MAP|test.svg",
    )

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.VIEWING
    assert transition.payload == {"map_file": "test.svg"}


def test_menu_scene_handles_map_controls_action(mock_app_context):
    """Verify that a MAP_CONTROLS action string creates a transition to MapScene."""
    # Arrange
    scene = MenuScene(mock_app_context)
    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action=MenuActions.MAP_CONTROLS,
    )

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.MAP
    assert transition.payload is None


def test_menu_scene_handles_calibrate_map_action(mock_app_context):
    """Verify CALIBRATE_MAP action transitions to MapGridCalibrationScene."""
    # Arrange
    scene = MenuScene(mock_app_context)
    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action="CALIBRATE_MAP|test.svg",
    )

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.CALIBRATE_MAP_GRID
    assert transition.payload == {"map_file": "test.svg"}


def test_menu_scene_handles_non_transition_action(mock_app_context):
    """Verify that actions like ROTATE_CW modify state but don't transition."""
    # Arrange
    scene = MenuScene(mock_app_context)
    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action=MenuActions.ROTATE_CW,
    )

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert transition is None
    mock_app_context.map_system.rotate.assert_called_once_with(90)


def test_menu_scene_scan_fails_without_map(mock_app_context):
    """Verify SCAN_SESSION action fails and sends notification if no map is loaded."""
    # Arrange
    mock_app_context.map_system.is_map_loaded.return_value = False  # Override for this test
    scene = MenuScene(mock_app_context)
    mock_menu_state = MenuState(
        current_menu_title="",
        active_items=[],
        item_rects=[],
        hovered_item_index=None,
        feedback_item_index=None,
        prime_progress=0.0,
        summon_progress=0.0,
        cursor_pos=None,
        is_visible=True,
        just_triggered_action=MenuActions.SCAN_SESSION,
    )

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert transition is None
    mock_app_context.notifications.add_notification.assert_called_once_with(
        "Load a map before scanning."
    )


def test_menu_scene_handles_calibrate_action(mock_app_context):
    """Verify CALIBRATE action transitions to IntrinsicsCalibrationScene."""
    # Arrange
    scene = MenuScene(mock_app_context)
    mock_menu_state = MagicMock(spec=MenuState)
    mock_menu_state.just_triggered_action = MenuActions.CALIBRATE
    # Mock other attributes to avoid attribute errors if accessed
    mock_menu_state.active_items = []
    mock_menu_state.is_visible = True

    # Act
    with patch.object(scene.menu_system, "update", return_value=mock_menu_state):
        transition = scene.update(inputs=[], current_time=0.0)

    # Assert
    assert isinstance(transition, SceneTransition)
    assert transition.target_scene == SceneId.CALIBRATE_INTRINSICS
