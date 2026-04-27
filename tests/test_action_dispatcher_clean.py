import pytest
from unittest.mock import MagicMock
from light_map.action_dispatcher import ActionDispatcher


class MockApp:
    def __init__(self):
        self.persistence_service = MagicMock()
        self.environment_manager = MagicMock()
        self.scene_manager = MagicMock()
        self.map_system = MagicMock()
        self.notifications = MagicMock()
        self.current_map_path = "/mock/map.svg"
        self.config = MagicMock()
        self.app_context = MagicMock()


@pytest.fixture
def app():
    return MockApp()


@pytest.fixture
def dispatcher(app):
    return ActionDispatcher(app)


def test_dispatch_sync_vision(dispatcher, app):
    payload = {"action": "SYNC_VISION"}
    state = MagicMock()
    dispatcher.dispatch(payload, state)
    app.environment_manager.sync_vision.assert_called_once_with(state)


def test_dispatch_trigger_menu(dispatcher, app):
    payload = {"action": "TRIGGER_MENU"}
    dispatcher.dispatch(payload)
    from light_map.core.common_types import SceneId

    app.scene_manager.transition_to.assert_called_once_with(SceneId.MENU)


def test_dispatch_update_grid(dispatcher, app):
    payload = {"action": "UPDATE_GRID", "spacing": 50}
    dispatcher.dispatch(payload)
    app.persistence_service.update_grid.assert_called_once_with(
        app.current_map_path, action="UPDATE_GRID", spacing=50
    )


def test_dispatch_toggle_grid(dispatcher, app):
    payload = {"action": "TOGGLE_GRID"}
    app.persistence_service.toggle_grid.return_value = True
    dispatcher.dispatch(payload)
    app.persistence_service.toggle_grid.assert_called_once_with(app.current_map_path)
    app.notifications.add_notification.assert_called_with("Visible Grid ON")


def test_dispatch_reset_fow(dispatcher, app):
    payload = {"action": "RESET_FOW"}
    state = MagicMock()
    dispatcher.dispatch(payload, state)
    app.environment_manager.reset_fow.assert_called_once_with(
        app.current_map_path, state
    )


def test_dispatch_toggle_fow(dispatcher, app):
    payload = {"action": "TOGGLE_FOW"}
    state = MagicMock()
    dispatcher.dispatch(payload, state)
    app.environment_manager.toggle_fow.assert_called_once_with(
        app.current_map_path, state
    )


def test_dispatch_update_token(dispatcher, app):
    payload = {"action": "UPDATE_TOKEN", "id": 42, "name": "Hero"}
    dispatcher.dispatch(payload)
    app.persistence_service.update_token.assert_called_once_with(
        42, action="UPDATE_TOKEN", id=42, name="Hero"
    )


def test_dispatch_update_system_config(dispatcher, app):
    payload = {"action": "UPDATE_SYSTEM_CONFIG", "projector_ppi": 100}
    app.persistence_service.update_system_config.return_value = True
    dispatcher.dispatch(payload)
    app.persistence_service.update_system_config.assert_called_once_with(payload)


def test_dispatch_inspect_token(dispatcher, app):
    payload = {"action": "INSPECT_TOKEN", "payload": "42"}
    dispatcher.dispatch(payload)
    from light_map.core.common_types import SceneId

    app.scene_manager.transition_to.assert_called_once_with(
        SceneId.EXCLUSIVE_VISION, payload={"token_id": 42}
    )


def test_dispatch_set_selection(dispatcher, app):
    from light_map.core.common_types import SelectionType
    
    state = MagicMock()
    payload = {"action": "SET_SELECTION", "type": "TOKEN", "id": 123}
    dispatcher.dispatch(payload, state)
    
    # We can't easily assert equality on SelectionState if it's a dataclass with no __eq__ 
    # that matches Mock, but we can check the attributes.
    assert state.selection.type == SelectionType.TOKEN
    assert state.selection.id == "123"

    # Test clearing selection
    payload = {"action": "SET_SELECTION", "type": "NONE", "id": None}
    dispatcher.dispatch(payload, state)
    assert state.selection.type == SelectionType.NONE
    assert state.selection.id is None


def test_legacy_map_file_loading(dispatcher, app):
    payload = {"map_file": "new_map.svg", "load_session": True}
    dispatcher.dispatch(payload)
    app.persistence_service.load_map.assert_called_once_with("new_map.svg", True)
