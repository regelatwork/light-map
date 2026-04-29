from unittest.mock import MagicMock

import numpy as np
import pytest

from light_map.core.app_context import AppContext
from light_map.core.common_types import GestureType
from light_map.map.map_scene import MapScene
from light_map.map.map_system import MapSystem
from light_map.state.world_state import WorldState


class MockHandInput:
    def __init__(self, proj_pos, gesture=GestureType.CLOSED_FIST):
        self.proj_pos = proj_pos
        self.gesture = gesture
        self.unit_direction = (0, 0)


@pytest.fixture
def context():
    ctx = MagicMock(spec=AppContext)
    ctx.app_config = MagicMock()
    ctx.app_config.width = 1000
    ctx.app_config.height = 1000
    ctx.app_config.projector_ppi = 96.0
    from light_map.core.common_types import AppConfig

    config = AppConfig(width=1000, height=1000, projector_matrix=np.eye(3))
    ctx.map_system = MapSystem(config)
    ctx.map_config_manager = MagicMock()
    ctx.map_config_manager.data.maps = {}
    ctx.map_config_manager.get_map_grid_spacing.return_value = 50.0
    ctx.events = MagicMock()
    ctx.notifications = MagicMock()
    ctx.save_session = MagicMock()
    ctx.state = WorldState()
    ctx.raw_tokens = []
    return ctx


def test_map_scene_undo_after_pan(context):
    scene = MapScene(context)

    # Initial state
    initial_state = context.map_system.state.to_viewport()

    # 1. Start Pan interaction
    hand = MockHandInput((500, 500), GestureType.CLOSED_FIST)
    scene.update([hand], [], 1.0)
    # First frame doesn't interact yet (sets base point)
    assert not scene.is_interacting

    # 2. Second frame of Pan
    hand2 = MockHandInput((600, 600), GestureType.CLOSED_FIST)
    scene.update([hand2], [], 1.1)
    assert scene.is_interacting
    assert scene.pre_interaction_state is not None

    # Verify pan happened
    assert context.map_system.state.x == 100.0

    # 3. End Pan
    scene.update([], [], 1.2)
    assert not scene.is_interacting
    assert context.map_system.can_undo()

    # 4. Undo
    context.map_system.undo()
    assert context.map_system.state.x == initial_state.x
    assert context.map_system.state.y == initial_state.y


def test_map_scene_undo_after_zoom(context):
    scene = MapScene(context)

    # Initial state
    initial_zoom = context.map_system.state.zoom

    # 1. Start Zoom interaction (2 hands pointing)
    hand1 = MockHandInput((400, 500), GestureType.POINTING)
    hand2 = MockHandInput((600, 500), GestureType.POINTING)
    scene.update([hand1, hand2], [], 1.0)

    # First frame of 2-hands only sets up the initial distance
    assert not scene.is_interacting

    # 2. Zoom in (increase distance)
    hand1b = MockHandInput((300, 500), GestureType.POINTING)
    hand2b = MockHandInput((700, 500), GestureType.POINTING)
    scene.update([hand1b, hand2b], [], 1.1)

    assert scene.is_interacting
    assert scene.pre_interaction_state is not None

    # Distance went from 200 to 400 => factor 2.0
    assert context.map_system.state.zoom == initial_zoom * 2.0

    # 3. End Zoom
    scene.update([], [], 1.2)
    assert not scene.is_interacting
    assert context.map_system.can_undo()

    # 4. Undo
    context.map_system.undo()
    assert context.map_system.state.zoom == initial_zoom


def test_no_undo_if_no_change(context):
    scene = MapScene(context)

    # Interaction that doesn't change anything
    hand = MockHandInput((500, 500), GestureType.CLOSED_FIST)
    scene.update([hand], [], 1.0)
    scene.update([hand], [], 1.1)
    scene.update([], [], 1.2)

    assert not context.map_system.can_undo()
