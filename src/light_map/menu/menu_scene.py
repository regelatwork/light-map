from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, List, Optional

import numpy as np

from light_map.core.common_types import (
    Action,
    GestureType,
    MenuActions,
    SceneId,
    TokenDetectionAlgorithm,
)
from light_map.core.scene import HandInput, Scene, SceneTransition
from light_map.input.input_manager import InputManager
from light_map.menu.menu_builder import build_root_menu
from light_map.menu.menu_system import MenuState, MenuSystem, MenuSystemState

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.interactive_app import InteractiveApp
    from light_map.core.common_types import Layer


class MenuScene(Scene):
    """Handles the main menu interactions."""

    def __init__(self, context: AppContext):
        super().__init__(context)

        from light_map.core.common_types import SelectionType

        selected_door = None
        door_is_open = False
        if (
            self.context.state
            and self.context.state.selection.type == SelectionType.DOOR
        ):
            selected_door = self.context.state.selection.id
            if selected_door:
                for blocker in self.context.visibility_engine.blockers:
                    if blocker.id == selected_door:
                        door_is_open = blocker.is_open
                        break

        dynamic_root = build_root_menu(
            self.context.map_config_manager,
            selected_door=selected_door,
            door_is_open=door_is_open,
            show_tokens=self.context.show_tokens,
            grid_overlay_visible=self.context.state.grid_overlay_visible if self.context.state else False,
        )

        self.menu_system = MenuSystem(
            self.context.app_config.width,
            self.context.app_config.height,
            dynamic_root,
        )
        self.input_manager = InputManager()
        self._menu_state = self.menu_system.get_current_state()

    def on_enter(self, payload: Any = None) -> None:
        """Called once when the scene becomes active."""
        self.menu_system.state = MenuSystemState.ACTIVE
        # Rebuild menu in case of changes (e.g., map list, debug state)
        from light_map.core.common_types import SelectionType

        selected_door = None
        door_is_open = False

        if (
            self.context.state
            and self.context.state.selection.type == SelectionType.DOOR
        ):
            selected_door = self.context.state.selection.id
            if selected_door:
                for blocker in self.context.visibility_engine.blockers:
                    if blocker.id == selected_door:
                        door_is_open = blocker.is_open
                        break

        new_root = build_root_menu(
            self.context.map_config_manager,
            selected_door=selected_door,
            door_is_open=door_is_open,
            show_tokens=self.context.show_tokens,
            grid_overlay_visible=self.context.state.grid_overlay_visible if self.context.state else False,
        )
        self.menu_system.set_root_menu(new_root)

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if Action.QUIT in actions:
            sys.exit(0)
        px, py = -1, -1
        gesture = GestureType.NONE
        is_present = bool(inputs)

        if is_present:
            px, py = inputs[0].proj_pos
            gesture = inputs[0].gesture

        self.input_manager.update(px, py, gesture, is_present)

        new_state = self.menu_system.update(
            self.input_manager.get_x(),
            self.input_manager.get_y(),
            self.input_manager.get_gesture(),
        )

        self._menu_state = new_state

        if not self._menu_state.just_triggered_action:
            return None

        action_raw = self._menu_state.just_triggered_action

        # Log the selection
        if self.context.analytics:
            self.context.analytics.log_menu_selection(action_raw)

        action, payload = (
            action_raw.split("|", 1) if "|" in action_raw else (action_raw, None)
        )

        # --- Translation Layer ---
        if action == MenuActions.MAP_CONTROLS:
            return SceneTransition(SceneId.MAP)
        if action == MenuActions.CLOSE_MENU:
            return SceneTransition(SceneId.VIEWING)
        if action == "LOAD_MAP":
            return SceneTransition(
                SceneId.VIEWING, payload={"map_file": payload, "load_session": True}
            )
        if action == "LOAD_SESSION":
            return SceneTransition(
                SceneId.VIEWING, payload={"map_file": payload, "load_session": True}
            )
        if action == "CALIBRATE_MAP":
            return SceneTransition(
                SceneId.CALIBRATE_MAP_GRID, payload={"map_file": payload}
            )
        if action == "FORGET_MAP" and payload:
            self.context.map_config_manager.forget_map(payload)
            self.on_enter()  # Rebuild menu
        elif action == "SCAN_FOR_MAPS":
            patterns = self.context.app_config.map_search_patterns
            if patterns:
                self.context.map_config_manager.scan_for_maps(patterns)
                self.on_enter()  # Rebuild menu
        elif action == MenuActions.CALIBRATE_INTRINSICS:
            return SceneTransition(SceneId.CALIBRATE_INTRINSICS)
        elif action == MenuActions.CALIBRATE_PROJECTOR:
            return SceneTransition(SceneId.CALIBRATE_PROJECTOR)
        elif action == MenuActions.CALIBRATE_PPI:
            return SceneTransition(SceneId.CALIBRATE_PPI)
        elif action == MenuActions.CALIBRATE_EXTRINSICS:
            return SceneTransition(SceneId.CALIBRATE_EXTRINSICS)
        elif action == MenuActions.CALIBRATE_PROJECTOR_3D:
            return SceneTransition(SceneId.CALIBRATE_PROJECTOR_3D)
        elif action == MenuActions.CALIBRATE_FLASH:
            return SceneTransition(SceneId.CALIBRATE_FLASH)
        elif action == MenuActions.SET_MAP_SCALE:
            return SceneTransition(SceneId.CALIBRATE_MAP_GRID)
        elif action == MenuActions.SCAN_SESSION:
            # The context holds the SVG loader, which indicates a loaded map
            if self.context.map_system.is_map_loaded():
                return SceneTransition(SceneId.SCANNING)

            self.context.notifications.add_notification("Load a map before scanning.")
        elif action == MenuActions.SCAN_ALGORITHM:
            current = self.context.map_config_manager.get_detection_algorithm()
            if current == TokenDetectionAlgorithm.FLASH:
                new_algo = TokenDetectionAlgorithm.STRUCTURED_LIGHT
            elif current == TokenDetectionAlgorithm.STRUCTURED_LIGHT:
                new_algo = TokenDetectionAlgorithm.ARUCO
            else:
                new_algo = TokenDetectionAlgorithm.FLASH

            self.context.map_config_manager.set_detection_algorithm(new_algo)
            # Rebuild menu to update title
            from light_map.core.common_types import SelectionType

            selected_door = None
            door_is_open = False
            if (
                self.context.state
                and self.context.state.selection.type == SelectionType.DOOR
            ):
                selected_door = self.context.state.selection.id
                if selected_door:
                    for blocker in self.context.visibility_engine.blockers:
                        if blocker.id == selected_door:
                            door_is_open = blocker.is_open
                            break

            new_root = build_root_menu(
                self.context.map_config_manager,
                selected_door=selected_door,
                door_is_open=door_is_open,
            )
            self.menu_system.set_root_menu(new_root)
        elif action == MenuActions.EXIT:
            sys.exit(0)
        # --- Actions that modify state but don't transition ---
        elif action == MenuActions.TOGGLE_DEBUG_MODE:
            self.context.debug_mode = not self.context.debug_mode
        elif action == MenuActions.TOGGLE_HAND_MASKING:
            gs = self.context.map_config_manager.data.global_settings
            gs.enable_hand_masking = not gs.enable_hand_masking
            self.context.map_config_manager.save()
            self.context.app_config.enable_hand_masking = gs.enable_hand_masking
            self.on_enter()
        elif action == MenuActions.TOGGLE_ARUCO_MASKING:
            gs = self.context.map_config_manager.data.global_settings
            gs.enable_aruco_masking = not gs.enable_aruco_masking
            self.context.map_config_manager.save()
            self.context.app_config.enable_aruco_masking = gs.enable_aruco_masking
            self.on_enter()
        elif action == MenuActions.SET_GM_POSITION:
            from light_map.core.common_types import GmPosition

            try:
                new_pos = GmPosition(payload)
                gs = self.context.map_config_manager.data.global_settings
                gs.gm_position = new_pos
                self.context.map_config_manager.save()
                self.context.app_config.gm_position = gs.gm_position
                self.on_enter()
            except ValueError:
                pass
        elif action == MenuActions.ROTATE_CW:
            self.context.map_system.push_state()
            self.context.map_system.rotate(90)
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.ROTATE_CCW:
            self.context.map_system.push_state()
            self.context.map_system.rotate(-90)
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.RESET_VIEW:
            self.context.map_system.push_state()
            self.context.map_system.reset_view_to_base()
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.RESET_ZOOM:
            self.context.map_system.push_state()
            self.context.map_system.reset_zoom_to_base()
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.UNDO_NAV:
            self.context.map_system.undo()
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.REDO_NAV:
            self.context.map_system.redo()
            if self.context.save_session:
                self.context.save_session()
        elif action == MenuActions.SYNC_VISION:
            return SceneTransition(SceneId.VIEWING, payload={"action": "SYNC_VISION"})
        elif action == MenuActions.RESET_FOW:
            return SceneTransition(SceneId.VIEWING, payload={"action": "RESET_FOW"})
        elif action == MenuActions.TOGGLE_FOW:
            return SceneTransition(SceneId.VIEWING, payload={"action": "TOGGLE_FOW"})
        elif action == MenuActions.TOGGLE_TOKENS:
            self.context.show_tokens = not self.context.show_tokens
            state_str = "ON" if self.context.show_tokens else "OFF"
            self.context.notifications.add_notification(f"GM: Tokens {state_str}")
            self.on_enter()  # Rebuild menu to update title
        elif action == MenuActions.TOGGLE_GRID:
            if self.context.state:
                import os
                self.context.state.grid_overlay_visible = not self.context.state.grid_overlay_visible
                # Persist to map config if a map is loaded
                if self.context.map_system.is_map_loaded():
                    map_path = self.context.map_system.svg_loader.filename
                    map_path = os.path.abspath(map_path)
                    entry = self.context.map_config_manager.data.maps.get(map_path)
                    if entry:
                        entry.grid_overlay_visible = self.context.state.grid_overlay_visible
                        self.context.map_config_manager.save()
                
                state_str = "ON" if self.context.state.grid_overlay_visible else "OFF"
                self.context.notifications.add_notification(f"Visible Grid {state_str}")
                self.on_enter()  # Rebuild menu
        elif action == MenuActions.TOGGLE_DOOR:
            return SceneTransition(
                SceneId.VIEWING, payload={"action": "TOGGLE_DOOR", "door": payload}
            )

        return None

    @property
    def menu_state(self) -> MenuState:
        """Exposes the current menu state for the MenuLayer."""
        return self.menu_system.get_current_state()

    @property
    def blocking(self) -> bool:
        """Menu scene should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Menu should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Menu only needs the menu itself and standard UI overlay layers (no masks/tokens)."""
        return [
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

    def render(self, frame: np.ndarray) -> np.ndarray:
        # Menu is now rendered by MenuLayer in the coordinator stack.
        # This scene just provides the state.
        return frame
