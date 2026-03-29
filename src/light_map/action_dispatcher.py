from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
import os
import logging

if TYPE_CHECKING:
    from .interactive_app import InteractiveApp
    from .core.scene import SceneTransition, WorldState
from .common_types import GridMetadata, SelectionState


ActionHandler = Callable[
    ["InteractiveApp", Dict[str, Any], Optional["WorldState"]],
    Optional["SceneTransition"],
]


class ActionDispatcher:
    def __init__(self, app: "InteractiveApp"):
        self.app = app
        self._handlers: Dict[str, ActionHandler] = {}
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
            self.app.load_map(payload["map_file"], payload.get("load_session", False))

        action_name = payload.get("action")
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
        self.register("TOGGLE_DEBUG_MODE", handle_toggle_debug_mode)
        self.register("INSPECT_TOKEN", handle_inspect_token)
        self.register("CLEAR_INSPECTION", handle_clear_inspection)
        self.register("TOGGLE_DOOR", handle_toggle_door)

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
        from .common_types import MenuActions, SceneId
        from .core.scene import SceneTransition

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
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if state is not None:
        app._sync_vision(state)
    app.app_context.notifications.add_notification("Vision Synchronized")
    return None


def handle_trigger_menu(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from .common_types import SceneId
    from .core.scene import SceneTransition

    return SceneTransition(SceneId.MENU)


def handle_reset_zoom(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.map_system.reset_zoom_to_base()
    app.notifications.add_notification("Zoom Reset to 1:1")
    return None


def handle_update_grid(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.current_map_path:
        entry = app.map_config.data.maps.get(app.current_map_path)
        if entry:
            entry.grid_origin_svg_x = payload.get("offset_x", 0.0)
            entry.grid_origin_svg_y = payload.get("offset_y", 0.0)

            spacing = payload.get("spacing")
            if spacing is not None and spacing > 0:
                entry.grid_spacing_svg = spacing
                app.refresh_base_scale()

            app.map_config.save()

            app.state.grid_metadata = GridMetadata(
                spacing_svg=entry.grid_spacing_svg,
                origin_svg_x=entry.grid_origin_svg_x,
                origin_svg_y=entry.grid_origin_svg_y,
            )

            app._rebuild_visibility_stack(entry)
            app.notifications.add_notification("Grid Configuration Updated")
    return None


def handle_inject_hands_world(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from .core.scene import HandInput
    from .common_types import GestureType

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
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if "zoom" in payload:
        app.map_system.state.zoom = payload["zoom"]
    if "pan_x" in payload and "pan_y" in payload:
        app.map_system.state.pan_x = payload["pan_x"]
        app.map_system.state.pan_y = payload["pan_y"]
    if "rotation" in payload:
        app.map_system.state.rotation = payload["rotation"]
    return None


def handle_reset_fow(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.fow_manager and app.current_map_path:
        app.fow_manager.reset()
        app.map_config.save_fow_masks(app.current_map_path, app.fow_manager)
        app.state.fow_mask = app.fow_manager.explored_mask.copy()
        app.notifications.add_notification("Fog of War Reset")
    return None


def handle_toggle_fow(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    if app.fow_manager:
        app.fow_manager.is_disabled = not app.fow_manager.is_disabled
        if app.state.fow_mask is not None:
            app.state.fow_mask = app.fow_manager.explored_mask.copy()
        state_str = "OFF" if app.fow_manager.is_disabled else "ON"
        app.notifications.add_notification(f"GM: Fog of War {state_str}")
    return None


def handle_update_system_config(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from .common_types import GmPosition

    gs = app.map_config.data.global_settings
    changed = False

    if "enable_hand_masking" in payload:
        gs.enable_hand_masking = payload["enable_hand_masking"]
        app.config.enable_hand_masking = gs.enable_hand_masking
        changed = True

    if "enable_aruco_masking" in payload:
        gs.enable_aruco_masking = payload["enable_aruco_masking"]
        app.config.enable_aruco_masking = gs.enable_aruco_masking
        changed = True

    if "parallax_factor" in payload:
        gs.parallax_factor = payload["parallax_factor"]
        app.config.parallax_factor = gs.parallax_factor
        changed = True

    if "gm_position" in payload:
        try:
            new_pos = GmPosition(payload["gm_position"])
            gs.gm_position = new_pos
            app.config.gm_position = new_pos
            changed = True
        except ValueError:
            pass

    if "use_projector_3d_model" in payload:
        gs.use_projector_3d_model = payload["use_projector_3d_model"]
        app.config.use_projector_3d_model = gs.use_projector_3d_model
        if app.config.projector_3d_model:
            app.config.projector_3d_model.use_3d = gs.use_projector_3d_model
        changed = True

    if changed:
        app.map_config.save()
        app.notifications.add_notification("System Settings Updated")

    return None


def handle_toggle_hand_masking(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    gs = app.map_config.data.global_settings
    gs.enable_hand_masking = not gs.enable_hand_masking
    app.map_config.save()
    app.config.enable_hand_masking = gs.enable_hand_masking
    state_str = "ON" if gs.enable_hand_masking else "OFF"
    app.notifications.add_notification(f"Projection Masking {state_str}")
    return None


def handle_set_gm_position(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from light_map.common_types import GmPosition

    try:
        new_pos = GmPosition(payload.get("payload", "None"))
        gs = app.map_config.data.global_settings
        gs.gm_position = new_pos
        app.map_config.save()
        app.config.gm_position = gs.gm_position
        app.notifications.add_notification(f"GM Position: {new_pos}")
    except (ValueError, KeyError):
        app.notifications.add_notification("Invalid GM Position")
    return None


def handle_toggle_debug_mode(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.app_context.debug_mode = not app.app_context.debug_mode
    state_str = "ON" if app.app_context.debug_mode else "OFF"
    app.notifications.add_notification(f"Debug Mode {state_str}")
    return None


def handle_inspect_token(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id_str = payload.get("payload")
    if token_id_str is not None:
        try:
            token_id = int(token_id_str)
            target_token = None
            if state is not None:
                for t in state.tokens:
                    if t.id == token_id:
                        target_token = t
                        break
                if not target_token:
                    for t in state.raw_tokens:
                        if t.id == token_id:
                            target_token = t
                            break

            if target_token:
                app.app_context.inspected_token_id = token_id
                map_file = (
                    app.map_system.svg_loader.filename
                    if app.map_system.svg_loader
                    else None
                )
                resolved = app.map_config.resolve_token_profile(token_id, map_file)
                app.notifications.add_notification(f"Inspecting: {resolved.name}")

                if app.visibility_engine and app.map_system.is_map_loaded():
                    engine = app.visibility_engine
                    app.app_context.inspected_token_mask = engine.get_token_vision_mask(
                        token_id,
                        target_token.world_x,
                        target_token.world_y,
                        size=resolved.size,
                        vision_range_grid=25.0,
                        mask_width=engine.width,
                        mask_height=engine.height,
                    )
        except ValueError:
            pass
    return None


def handle_clear_inspection(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    app.app_context.inspected_token_id = None
    app.app_context.inspected_token_mask = None
    return None


def handle_toggle_door(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    from light_map.common_types import SelectionType

    door_id = payload.get("door_id") or payload.get("payload")
    if door_id:
        app.state.selection = SelectionState(type=SelectionType.DOOR, id=door_id)

    if app.state.selection.type == SelectionType.DOOR and app.state.selection.id:
        door_id = app.state.selection.id
        found = False
        for blocker in app.visibility_engine.blockers:
            if blocker.id == door_id:
                blocker.is_open = not blocker.is_open
                found = True
        if found:
            app.visibility_engine.update_blockers(
                app.visibility_engine.blockers,
                app.fow_manager.width,
                app.fow_manager.height,
            )
            app._sync_blockers_to_state()
            app.notifications.add_notification(f"Door {door_id} Toggled")
            app.save_session()
            if state is not None:
                app._sync_vision(state)
    else:
        app.notifications.add_notification("No door selected to toggle")
    return None


# --- NEW HANDLERS ---


def handle_zoom(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    delta = payload.get("delta", 0.0)
    app.map_system.zoom_pinned(
        1.0 + delta, (app.config.width // 2, app.config.height // 2)
    )
    return None


def handle_update_token(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    if token_id is not None:
        # Try to get existing definition to preserve fields
        existing_def = None
        is_map_override = False

        map_file = app.current_map_path
        if map_file:
            map_entry = app.map_config.data.maps.get(map_file)
            if map_entry:
                existing_def = map_entry.aruco_overrides.get(token_id)
                if existing_def:
                    is_map_override = True

        # Explicit override from action data (if provided)
        action_override = payload.get("is_map_override")
        if action_override is not None:
            is_map_override = action_override

        if not existing_def:
            existing_def = app.map_config.data.global_settings.aruco_defaults.get(
                token_id
            )

        new_name = payload.get("name")
        new_color = payload.get("color")
        new_type = payload.get("type")
        new_profile = payload.get("profile")
        new_size = payload.get("size")
        new_height_mm = payload.get("height_mm")

        # Use existing values if not provided in the update
        final_name = (
            new_name
            if new_name is not None
            else (existing_def.name if existing_def else f"Token {token_id}")
        )
        final_type = (
            new_type
            if new_type is not None
            else (existing_def.type if existing_def else "NPC")
        )
        # Determination of final profile and dimensions must respect the exclusivity invariant
        final_profile = new_profile
        final_size = new_size
        final_height_mm = new_height_mm

        if final_profile is not None:
            # If profile is explicitly provided (even if ''), it clears individual overrides
            if final_profile == "":
                final_profile = None
            else:
                final_size = None
                final_height_mm = None
        elif final_size is not None or final_height_mm is not None:
            # If custom dimensions are explicitly provided, clear profile
            final_profile = None
        else:
            # Nothing was provided in this update, fallback to existing
            if existing_def:
                final_profile = existing_def.profile
                final_size = existing_def.size
                final_height_mm = existing_def.height_mm
            else:
                final_profile = None
                final_size = None
                final_height_mm = None

        final_color = (
            new_color
            if new_color is not None
            else (existing_def.color if existing_def else None)
        )

        if is_map_override and map_file:
            app.map_config.set_map_aruco_override(
                map_name=map_file,
                aruco_id=token_id,
                name=final_name,
                type=final_type,
                profile=final_profile,
                size=final_size,
                height_mm=final_height_mm,
                color=final_color,
            )
            logging.info(
                f"ActionDispatcher: Updated MAP override for token {token_id} on {os.path.basename(map_file)}"
            )
        else:
            app.map_config.set_global_aruco_definition(
                aruco_id=token_id,
                name=final_name,
                type=final_type,
                profile=final_profile,
                size=final_size,
                height_mm=final_height_mm,
                color=final_color,
            )
            logging.info(
                f"ActionDispatcher: Updated GLOBAL definition for token {token_id}"
            )
    return None


def handle_delete_token_override(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    map_file = app.current_map_path
    if token_id is not None and map_file:
        app.map_config.delete_map_aruco_override(map_file, token_id)
        logging.info(
            f"ActionDispatcher: Deleted MAP override for token {token_id} on {os.path.basename(map_file)}"
        )
    return None


def handle_delete_token(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    token_id = payload.get("id")
    if token_id is not None:
        app.map_config.delete_global_aruco_definition(token_id)
        logging.info(
            f"ActionDispatcher: Deleted GLOBAL definition for token {token_id}"
        )
    return None


def handle_update_token_profile(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    name = payload.get("name")
    size = payload.get("size")
    height_mm = payload.get("height_mm")

    if name is not None and size is not None and height_mm is not None:
        app.map_config.set_token_profile(name, size, height_mm)
        logging.info(
            f"ActionDispatcher: Updated profile '{name}' (S:{size} H:{height_mm}mm)"
        )
    return None


def handle_delete_token_profile(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    name = payload.get("name")
    if name is not None:
        app.map_config.delete_token_profile(name)
        logging.info(f"ActionDispatcher: Deleted profile '{name}'")
    return None


def handle_menu_interact(
    app: "InteractiveApp", payload: Dict[str, Any], state: Optional["WorldState"] = None
) -> Optional["SceneTransition"]:
    # Use class name check to avoid potential double-import/instance-check issues
    is_menu_scene = app.current_scene.__class__.__name__ == "MenuScene"

    logging.debug(
        f"ActionDispatcher: Received MENU_INTERACT index={payload.get('index')}, current_scene={app.current_scene.__class__.__name__}"
    )

    if is_menu_scene:
        index = payload.get("index")
        if index is not None:
            # Safely access menu_system (expected on MenuScene)
            menu_sys = getattr(app.current_scene, "menu_system", None)
            if menu_sys:
                menu_sys.trigger_index(index)
                app.current_scene.increment_version()
            else:
                logging.error(
                    "ActionDispatcher: Current scene is MenuScene but has no menu_system"
                )
    else:
        logging.warning(
            f"ActionDispatcher: MENU_INTERACT ignored - current scene {app.current_scene.__class__.__name__} is not MenuScene"
        )
    return None
