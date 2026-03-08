import pytest
from unittest.mock import MagicMock, patch
from light_map.scenes.map_scene import MapScene, ScreenCenteredMapAdapter
from light_map.core.app_context import AppContext
from light_map.map_system import MapSystem
from light_map.core.scene import HandInput
from light_map.gestures import GestureType


@pytest.fixture
def map_scene_context():
    context = MagicMock(spec=AppContext)
    context.events = MagicMock()
    context.map_system = MagicMock(spec=MapSystem)
    context.map_system.width = 1000
    context.map_system.height = 1000
    context.map_system.screen_to_world.return_value = (0.0, 0.0)
    context.map_system.svg_loader = None
    context.raw_tokens = []
    context.state = MagicMock()
    context.state.tokens = []
    context.app_config = MagicMock()
    context.app_config.projector_ppi = 96.0
    context.map_config_manager = MagicMock()
    context.map_config_manager.get_map_grid_spacing.return_value = 0.0
    context.map_config_manager.get_ppi.return_value = 96.0
    return context


def test_map_scene_uses_adapter(map_scene_context):
    scene = MapScene(map_scene_context)

    # Mock inputs for zoom
    inputs = [
        HandInput(GestureType.POINTING, (100, 100), (0.0, 0.0), None),
        HandInput(GestureType.POINTING, (200, 200), (0.0, 0.0), None),
    ]

    # Mock interaction controller process_gestures
    with patch.object(scene.interaction_controller, "process_gestures") as mock_process:
        scene.update(inputs, [], 0.0)

        # Verify it was called with an adapter, not the raw map system
        args, _ = mock_process.call_args
        target = args[1]
        assert isinstance(target, ScreenCenteredMapAdapter)
        assert target.map_system == map_scene_context.map_system


def test_screen_centered_adapter_logic(map_scene_context):
    adapter = ScreenCenteredMapAdapter(map_scene_context.map_system)

    # Test Zoom Pinned
    # Passed center (150, 150) from gesture
    adapter.zoom_pinned(1.5, (150, 150))

    # Should call map_system.zoom_pinned with (500, 500) (Screen Center)
    map_scene_context.map_system.zoom_pinned.assert_called_with(1.5, (500, 500))


def test_screen_centered_adapter_pan(map_scene_context):
    adapter = ScreenCenteredMapAdapter(map_scene_context.map_system)
    adapter.pan(10, 20)
    map_scene_context.map_system.pan.assert_called_with(10, 20)
