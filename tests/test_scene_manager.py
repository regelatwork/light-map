import pytest
from unittest.mock import MagicMock, patch
from light_map.core.scene_manager import SceneManager
from light_map.core.common_types import SceneId
from light_map.state.world_state import WorldState


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.layer_manager = MagicMock()
    return context


@pytest.fixture
def state():
    return WorldState()


def test_scene_manager_initialization(mock_context, state):
    manager = SceneManager(mock_context, state)
    assert manager.current_scene_id == SceneId.MENU
    assert manager.current_scene is not None
    assert len(manager.scenes) > 0
    assert SceneId.MENU in manager.scenes


def test_scene_manager_transition(mock_context, state):
    manager = SceneManager(mock_context, state)

    # Mock scenes
    menu_scene = manager.scenes[SceneId.MENU] = MagicMock()
    viewing_scene = manager.scenes[SceneId.VIEWING] = MagicMock()

    manager.current_scene = menu_scene
    manager.current_scene_id = SceneId.MENU

    payload = {"map_path": "test.svg"}
    manager.transition_to(SceneId.VIEWING, payload)

    menu_scene.on_exit.assert_called_once()
    viewing_scene.on_enter.assert_called_once_with(payload)
    assert manager.current_scene_id == SceneId.VIEWING
    assert manager.current_scene == viewing_scene
    # Verify WorldState update (class name of MagicMock is 'MagicMock')
    assert state.current_scene_name == "MagicMock"


def test_scene_manager_current_scene_name(mock_context, state):
    manager = SceneManager(mock_context, state)
    manager.current_scene_id = SceneId.MENU
    assert manager.current_scene_name == "MENU"

    manager.current_scene_id = SceneId.VIEWING
    assert manager.current_scene_name == "VIEWING"


def test_scene_manager_get_layer_stack(mock_context, state):
    manager = SceneManager(mock_context, state)
    mock_layers = [MagicMock(), MagicMock()]
    mock_context.layer_manager.get_stack.return_value = mock_layers

    stack = manager.get_layer_stack()

    mock_context.layer_manager.get_stack.assert_called_once_with(manager.current_scene)
    assert stack == mock_layers


def test_scene_manager_handle_transition(mock_context, state):
    manager = SceneManager(mock_context, state)

    # Mock transition object
    transition = MagicMock()
    transition.target_scene = SceneId.MAP
    transition.payload = {"foo": "bar"}

    # Mock transition_to
    with patch.object(manager, "transition_to") as mock_transition_to:
        manager.handle_transition(transition)
        mock_transition_to.assert_called_once_with(SceneId.MAP, {"foo": "bar"})
