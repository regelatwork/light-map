import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.scenes.menu_scene import MenuScene
from light_map.core.app_context import AppContext
from light_map.common_types import MenuActions
from light_map.map_system import MapSystem
from light_map.core.world_state import WorldState


@pytest.fixture
def context():
    ctx = MagicMock(spec=AppContext)
    ctx.app_config = MagicMock()
    ctx.app_config.width = 1000
    ctx.app_config.height = 1000
    from light_map.common_types import AppConfig

    config = AppConfig(width=1000, height=1000, projector_matrix=np.eye(3))
    ctx.map_system = MapSystem(config)
    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.data.maps = {}
    ctx.map_config_manager.get_detection_algorithm.return_value = "ARUCO"
    ctx.analytics = MagicMock()
    ctx.save_session = MagicMock()
    ctx.state = WorldState()
    ctx.visibility_engine = MagicMock()
    ctx.visibility_engine.blockers = []
    return ctx


def test_menu_scene_undo_redo(context):
    scene = MenuScene(context)

    # 1. Simulate an interaction to have something to undo
    context.map_system.push_state()
    context.map_system.pan(100, 100)
    assert context.map_system.can_undo()

    # 2. Trigger UNDO from menu
    # We mock the menu system to return UNDO_NAV action
    scene.menu_system = MagicMock()
    scene.menu_system.update.return_value = MagicMock(
        just_triggered_action=MenuActions.UNDO_NAV,
        hovered_item_index=0,
        node_stack_titles=[],
    )

    scene.update([], [], 1.0)

    # Verify undo happened
    assert context.map_system.state.x == 0
    assert context.map_system.can_redo()

    # 3. Trigger REDO from menu
    scene.menu_system.update.return_value = MagicMock(
        just_triggered_action=MenuActions.REDO_NAV,
        hovered_item_index=0,
        node_stack_titles=[],
    )

    scene.update([], [], 1.1)

    # Verify redo happened
    assert context.map_system.state.x == 100


def test_menu_scene_discrete_actions_push_state(context):
    scene = MenuScene(context)

    # 1. Trigger ROTATE_CW from menu
    scene.menu_system = MagicMock()
    scene.menu_system.update.return_value = MagicMock(
        just_triggered_action=MenuActions.ROTATE_CW,
        hovered_item_index=0,
        node_stack_titles=[],
    )

    scene.update([], [], 1.0)

    assert context.map_system.state.rotation == 90
    assert context.map_system.can_undo()

    # 2. Undo it
    context.map_system.undo()
    assert context.map_system.state.rotation == 0
