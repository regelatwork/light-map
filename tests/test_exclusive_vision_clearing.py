from unittest.mock import MagicMock

import numpy as np
import pytest

from light_map.core.app_context import AppContext
from light_map.core.common_types import (
    Action,
    AppConfig,
    GestureType,
    SceneId,
    SelectionType,
)
from light_map.core.scene import HandInput
from light_map.map.map_scene import ViewingScene
from light_map.state.temporal_event_manager import TemporalEventManager
from light_map.state.world_state import WorldState
from light_map.visibility.exclusive_vision_scene import ExclusiveVisionScene


@pytest.fixture
def mock_app_context():
    config = MagicMock(spec=AppConfig)
    config.width = 1920
    config.height = 1080
    config.projector_ppi = 96.0
    config.inspection_linger_duration = 10.0

    context = MagicMock(spec=AppContext)
    context.app_config = config
    context.state = WorldState()
    context.events = TemporalEventManager()
    context.notifications = MagicMock()
    context.map_system = MagicMock()
    context.map_system.width = 1920
    context.map_system.height = 1080
    context.map_system.screen_to_world.return_value = (100.0, 100.0)

    # Setup MapConfigManager mock
    map_config = MagicMock()
    map_config.data.maps = {}
    map_config.get_map_grid_spacing.return_value = 50.0
    context.map_config_manager = map_config

    # Setup LayerStackManager mock
    layer_manager = MagicMock()
    context.layer_manager = layer_manager
    context.raw_tokens = []

    # Initialize some inspected state in context AND state
    context.inspected_token_id = 123
    context.inspected_token_mask = np.zeros((100, 100), dtype=np.uint8)
    context.state.inspected_token_id = 123

    return context


def test_exclusive_vision_scene_clears_on_exit(mock_app_context):
    scene = ExclusiveVisionScene(mock_app_context)
    scene.token_id = 123

    # Simulate exiting the scene
    scene.on_exit()

    # ASSERT: Everything should be cleared
    assert mock_app_context.inspected_token_id is None
    assert mock_app_context.inspected_token_mask is None
    assert mock_app_context.state.inspected_token_id is None


def test_viewing_scene_transitions_to_exclusive_vision(mock_app_context):
    scene = ViewingScene(mock_app_context)

    # Mock _handle_dwell_trigger to return a token
    scene._handle_dwell_trigger = MagicMock(return_value=(SelectionType.TOKEN, "456"))

    # Need non-empty inputs to reach dwell logic
    hand = HandInput(
        gesture=GestureType.POINTING,
        proj_pos=(100, 100),
        unit_direction=(0.0, 0.0),
        raw_landmarks=None,
    )

    # Simulate a dwell trigger
    transition = scene.update(
        inputs=[hand], actions=[Action.DWELL_TRIGGER], current_time=time_provider()
    )

    assert transition is not None
    assert transition.target_scene == SceneId.EXCLUSIVE_VISION
    assert transition.payload == {"token_id": 456}


def test_exclusive_vision_scene_transitions_back_on_clear(mock_app_context):
    scene = ExclusiveVisionScene(mock_app_context)

    # Simulate Action.CLEAR_INSPECTION
    transition = scene.update(
        inputs=[], actions=[Action.CLEAR_INSPECTION], current_time=time_provider()
    )

    assert transition is not None
    assert transition.target_scene == SceneId.VIEWING


def time_provider():
    return 1000.0
