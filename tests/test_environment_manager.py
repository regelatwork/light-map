import pytest
import numpy as np
from unittest.mock import MagicMock
from light_map.vision.environment_manager import EnvironmentManager
from light_map.state.world_state import WorldState, Token
from light_map.core.app_context import MainContext
from light_map.core.common_types import AppConfig, MapRenderState
from light_map.visibility.visibility_types import VisibilityBlocker, VisibilityType
from light_map.visibility.fow_manager import FogOfWarManager
from light_map.visibility.visibility_engine import VisibilityEngine


@pytest.fixture
def mock_context():
    context = MagicMock(spec=MainContext)
    context.app_config = MagicMock(spec=AppConfig)
    context.app_config.width = 100
    context.app_config.height = 100
    context.map_config_manager = MagicMock()
    context.map_system = MagicMock()
    context.notifications = MagicMock()
    context.save_session = MagicMock()
    context.visibility_engine = VisibilityEngine(grid_spacing_svg=10.0)
    context.layer_manager = MagicMock()
    return context


@pytest.fixture
def state():
    s = WorldState()
    s.map_render_state = MapRenderState(filepath="test_map.svg")
    return s


def test_sync_vision_updates_masks(mock_context, state):
    manager = EnvironmentManager(mock_context, state)
    manager.fow_manager = FogOfWarManager(100, 100)

    # Add a PC token
    token = Token(id=1, world_x=50, world_y=50, type="PC")
    state.tokens = [token]

    # Mock visibility engine response
    mask = np.ones((100, 100), dtype=np.uint8) * 255
    manager.visibility_engine.get_aggregate_vision_mask = MagicMock(
        return_value=(mask, {1})
    )

    manager.sync_vision(state)

    assert state.visibility_mask is not None
    assert np.all(state.visibility_mask == 255)
    assert state.fow_mask is not None
    assert 1 in state.discovered_ids
    mock_context.map_config_manager.save_fow_masks.assert_called_once()


def test_rebuild_visibility_stack(mock_context, state):
    manager = EnvironmentManager(mock_context, state)
    entry = MagicMock()
    entry.grid_spacing_svg = 20.0
    entry.grid_origin_svg_x = 5.0
    entry.grid_origin_svg_y = 5.0
    entry.grid_type = "square"
    entry.grid_overlay_visible = True
    entry.grid_overlay_color = (255, 255, 255)
    entry.fow_disabled = False

    mock_context.map_system.svg_loader.get_visibility_blockers.return_value = []
    mock_context.map_system.svg_loader.svg.width = 200
    mock_context.map_system.svg_loader.svg.height = 200

    manager.rebuild_visibility_stack(entry, "test_map.svg")

    assert manager.visibility_engine.grid_spacing_svg == 20.0
    assert state.grid_metadata.spacing_svg == 20.0
    assert manager.fow_manager is not None
    assert manager.fow_manager.width > 0
    mock_context.map_config_manager.load_fow_masks.assert_called_once()


def test_toggle_door(mock_context, state):
    manager = EnvironmentManager(mock_context, state)
    manager.fow_manager = FogOfWarManager(100, 100)

    door = VisibilityBlocker(
        points=[(0, 0), (10, 10)],
        type=VisibilityType.DOOR,
        layer_name="doors",
        id="door1",
        is_open=False,
    )
    manager.visibility_engine.blockers = [door]

    # Ensure sync_vision is mocked to avoid errors during toggle
    manager.sync_vision = MagicMock()

    manager.toggle_door("door1", state)

    assert manager.visibility_engine.blockers[0].is_open is True
    assert state.blockers[0].is_open is True
    mock_context.notifications.add_notification.assert_called()
    mock_context.save_session.assert_called_once()
    manager.sync_vision.assert_called_once_with(state)
