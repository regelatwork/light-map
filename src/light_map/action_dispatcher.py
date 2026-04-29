import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from light_map.core.scene import SceneTransition, WorldState
    from light_map.interactive_app import InteractiveApp

ActionHandler = Callable[
    ["InteractiveApp", dict[str, Any], Optional["WorldState"]],
    Optional["SceneTransition"],
]


class ActionDispatcher:
    def __init__(self, app: "InteractiveApp"):
        self.app = app
        self._handlers: dict[str, ActionHandler] = {}
        self._register_default_handlers()

    def register(self, action_name: str, handler: ActionHandler):
        self._handlers[action_name] = handler

    def dispatch(
        self, payload: Any, state: Optional["WorldState"] = None
    ) -> Optional["SceneTransition"]:
        if not isinstance(payload, dict):
            return None

        action_name = payload.get("action")
        logging.info(f"ActionDispatcher: Dispatching action: {action_name}")

        # Handle legacy "map_file" which isn't always in an "action" field
        if "map_file" in payload:
            self.app.persistence_service.load_map(
                payload["map_file"], payload.get("load_session", False)
            )

        if not action_name:
            return None

        handler = self._handlers.get(action_name)
        if handler:
            return handler(self.app, payload, state)

        # Fallback for MenuActions which are handled by a generic transition logic
        return self._handle_menu_transition(action_name)

    def _register_default_handlers(self):
        self.register("SYNC_VISION", handle_sync_vision)
        self.register("TRIGGER_MENU", handle_trigger_menu)
        self.register("RESET_ZOOM", handle_reset_zoom)
        self.register("UPDATE_GRID", handle_update_grid)
        self.register("INJECT_HANDS_WORLD", handle_inject_hands_world)
        self.register("SET_VIEWPORT", handle_set_viewport)
        self.register("RESET_FOW", handle_reset_fow)
        self.register("TOGGLE_FOW", handle_toggle_fow)
        self.register("TOGGLE_HAND_MASKING", handle_toggle_hand_masking)
        self.register("SET_GM_POSITION", handle_set_gm_position)
        self.register("SET_SELECTION", handle_set_selection)
        self.register("TOGGLE_DEBUG_MODE", handle_toggle_debug_mode)
        self.register("INSPECT_TOKEN", handle_inspect_token)
        self.register("CLEAR_INSPECTION", handle_clear_inspection)
        self.register("TOGGLE_DOOR", handle_toggle_door)
        self.register("TOGGLE_GRID", handle_toggle_grid)
        self.register("SET_GRID_COLOR", handle_set_grid_color)
        self.register("QUIT", handle_quit)

        # Remote Driver / System Actions
        self.register("ZOOM", handle_zoom)
        self.register("UPDATE_TOKEN", handle_update_token)
        self.register("DELETE_TOKEN_OVERRIDE", handle_delete_token_override)
        self.register("DELETE_TOKEN", handle_delete_token)
        self.register("UPDATE_TOKEN_PROFILE", handle_update_token_profile)
        self.register("DELETE_TOKEN_PROFILE", handle_delete_token_profile)
        self.register("UPDATE_SYSTEM_CONFIG", handle_update_system_config)
        self.register("MENU_INTERACT", handle_menu_interact)

    def _handle_menu_transition(self, action_name: str) -> Optional["SceneTransition"]:
        from light_map.core.common_types import MenuActions, SceneId
        from light_map.core.scene import SceneTransition

        scene_map = {
            MenuActions.CALIBRATE_INTRINSICS: SceneId.CALIBRATE_INTRINSICS,
            MenuActions.CALIBRATE_PROJECTOR: SceneId.CALIBRATE_PROJECTOR,
            MenuActions.CALIBRATE_PPI: SceneId.CALIBRATE_PPI,
            MenuActions.CALIBRATE_EXTRINSICS: SceneId.CALIBRATE_EXTRINSICS,
            MenuActions.CALIBRATE_PROJECTOR_3D: SceneId.CALIBRATE_PROJECTOR_3D,
            MenuActions.CALIBRATE_FLASH: SceneId.CALIBRATE_FLASH,
            MenuActions.SET_MAP_SCALE: SceneId.CALIBRATE_MAP_GRID,
            MenuActions.CALIBRATE_SCALE: SceneId.CALIBRATE_MAP_GRID,
            "SCAN_SESSION": SceneId.SCANNING,
        }

        if action_name in scene_map:
            if (
                action_name == "SCAN_SESSION"
                and not self.app.map_system.is_map_loaded()
            ):
                self.app.notifications.add_notification("Load a map before scanning.")
                return None
            return SceneTransition(scene_map[action_name])

        return None


def handle_sync_vision(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.environment_manager.sync_vision(state)
    return None


def handle_trigger_menu(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from light_map.core.common_types import SceneId

    app.scene_manager.transition_to(SceneId.MENU)
    return None


def handle_reset_zoom(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.map_system.reset_zoom_to_base()
    app.notifications.add_notification("Zoom Reset to 1:1")
    return None


def handle_update_grid(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.current_map_path:
        app.persistence_service.update_grid(app.current_map_path, **payload)
        app.notifications.add_notification("Grid Configuration Updated")
    return None


def handle_toggle_grid(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.current_map_path:
        visible = app.persistence_service.toggle_grid(app.current_map_path)
        state_str = "ON" if visible else "OFF"
        app.notifications.add_notification(f"Visible Grid {state_str}")
    else:
        app.notifications.add_notification("Load a map to toggle grid.")
    return None


def handle_set_grid_color(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    color = payload.get("color") or payload.get("payload")
    if app.current_map_path and color:
        app.persistence_service.set_grid_color(app.current_map_path, color)
        app.notifications.add_notification(f"Grid Color Set: {color}")
    return None


def handle_inject_hands_world(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from light_map.core.common_types import GestureType
    from light_map.core.scene import HandInput

    hands_data = payload.get("hands", [])
    processed_hands = []
    for h in hands_data:
        sx, sy = app.map_system.world_to_screen(h["world_x"], h["world_y"])
        gesture_str = h.get("gesture", "NONE").upper()
        try:
            gesture = GestureType[gesture_str]
        except KeyError:
            gesture = GestureType.NONE
        processed_hands.append(
            HandInput(
                gesture=gesture,
                proj_pos=(int(sx), int(sy)),
                unit_direction=(0.0, 0.0),
                raw_landmarks=None,
            )
        )
    if state is not None:
        state.update_inputs(processed_hands, app.time_provider())
    return None


def handle_set_viewport(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if "zoom" in payload:
        app.map_system.state.zoom = payload["zoom"]
    if "x" in payload and "y" in payload:
        app.map_system.state.x = payload["x"]
        app.map_system.state.y = payload["y"]
    if "rotation" in payload:
        app.map_system.state.rotation = payload["rotation"]
    return None


def handle_reset_fow(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.current_map_path:
        app.environment_manager.reset_fow(app.current_map_path, state)
    return None


def handle_toggle_fow(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.current_map_path:
        app.environment_manager.toggle_fow(app.current_map_path, state)
    return None


def handle_update_system_config(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.persistence_service.update_system_config(payload):
        app.notifications.add_notification("System Settings Updated")
    return None


def handle_toggle_hand_masking(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    visible = app.persistence_service.toggle_hand_masking()
    state_str = "ON" if visible else "OFF"
    app.notifications.add_notification(f"Projection Masking {state_str}")
    return None


def handle_set_gm_position(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    new_pos = app.persistence_service.set_gm_position(payload.get("payload", "None"))
    if new_pos:
        app.notifications.add_notification(f"GM Position: {new_pos}")
    else:
        app.notifications.add_notification("Invalid GM Position")
    return None


def handle_set_selection(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    import json

    from light_map.core.common_types import SelectionState, SelectionType

    if state is not None:
        # The frontend might send fields top-level or inside a stringified 'payload'
        data = payload
        if "payload" in payload and isinstance(payload["payload"], str):
            try:
                data = json.loads(payload["payload"])
            except json.JSONDecodeError:
                pass

        sel_type_str = data.get("type", "NONE").upper()
        sel_id = data.get("id")
        try:
            sel_type = SelectionType[sel_type_str]
        except KeyError:
            sel_type = SelectionType.NONE

        state.selection = SelectionState(
            type=sel_type, id=str(sel_id) if sel_id is not None else None
        )
    return None


def handle_toggle_debug_mode(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.app_context.debug_mode = not app.app_context.debug_mode
    state_str = "ON" if app.app_context.debug_mode else "OFF"
    app.notifications.add_notification(f"Debug Mode {state_str}")
    return None


def handle_inspect_token(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from light_map.core.common_types import SceneId

    token_id_str = payload.get("payload")
    if token_id_str is not None:
        try:
            token_id = int(token_id_str)
            app.scene_manager.transition_to(
                SceneId.EXCLUSIVE_VISION, payload={"token_id": token_id}
            )
        except ValueError:
            pass
    return None


def handle_clear_inspection(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.app_context.inspected_token_id = None
    app.app_context.inspected_token_mask = None
    return None


def handle_toggle_door(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    door_id = payload.get("door_id") or payload.get("payload")
    app.environment_manager.toggle_door(door_id, state)
    return None


def handle_zoom(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    delta = payload.get("delta", 0.0)
    app.map_system.zoom_pinned(
        1.0 + delta, (app.config.width // 2, app.config.height // 2)
    )
    return None


def handle_update_token(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    if token_id is not None:
        app.persistence_service.update_token(token_id, **payload)
    return None


def handle_delete_token_override(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    if token_id is not None:
        app.persistence_service.delete_token_override(token_id)
    return None


def handle_delete_token(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    if token_id is not None:
        app.persistence_service.delete_token(token_id)
    return None


def handle_update_token_profile(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    name = payload.get("name")
    size = payload.get("size")
    height_mm = payload.get("height_mm")
    app.persistence_service.update_token_profile(name, size, height_mm)
    return None


def handle_delete_token_profile(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    name = payload.get("name")
    app.persistence_service.delete_token_profile(name)
    return None


def handle_menu_interact(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    is_menu_scene = app.scene_manager.current_scene_id.value == "MENU"
    if is_menu_scene:
        index = payload.get("index")
        if index is not None:
            menu_sys = getattr(app.scene_manager.current_scene, "menu_system", None)
            if menu_sys:
                menu_sys.trigger_index(index)
    return None


def handle_quit(
    app: "InteractiveApp", payload: dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if state is not None:
        state.is_running = False
    return None
