from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, List, Optional

import numpy as np

from light_map.common_types import GestureType, MenuActions, SceneId
from light_map.core.scene import HandInput, Scene, SceneTransition
from light_map.input_manager import InputManager
from light_map.menu_builder import build_root_menu
from light_map.menu_system import MenuSystem, MenuSystemState

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext


class MenuScene(Scene):
    """Handles the main menu interactions."""

    def __init__(self, context: AppContext):
        super().__init__(context)

        dynamic_root = build_root_menu(self.context.map_config_manager)

        self.menu_system = MenuSystem(
            self.context.app_config.width,
            self.context.app_config.height,
            dynamic_root,
        )
        self.input_manager = InputManager()
        self._menu_state = self.menu_system.get_current_state()

    def on_enter(self, payload: Any = None) -> None:
        """Called once when the scene becomes active."""
        self.menu_system.state = MenuSystemState.WAITING_FOR_NEUTRAL
        # Rebuild menu in case of changes (e.g., map list, debug state)
        new_root = build_root_menu(self.context.map_config_manager)
        self.menu_system.set_root_menu(new_root)

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        px, py = -1, -1
        gesture = GestureType.NONE
        is_present = bool(inputs)

        if is_present:
            px, py = inputs[0].proj_pos
            gesture = inputs[0].gesture

        self.input_manager.update(px, py, gesture, is_present)

        self._menu_state = self.menu_system.update(
            self.input_manager.get_x(),
            self.input_manager.get_y(),
            self.input_manager.get_gesture(),
        )

        if not self._menu_state.just_triggered_action:
            return None

        action_raw = self._menu_state.just_triggered_action
        action, payload = (
            action_raw.split("|", 1) if "|" in action_raw else (action_raw, None)
        )

        # --- Translation Layer ---
        if action == MenuActions.MAP_CONTROLS:
            return SceneTransition(SceneId.MAP)
        if action == MenuActions.CLOSE_MENU:
            return SceneTransition(SceneId.VIEWING)
        if action == "LOAD_MAP":
            return SceneTransition(SceneId.VIEWING, payload={"map_file": payload})
        if action == "LOAD_SESSION":
            return SceneTransition(
                SceneId.VIEWING, payload={"map_file": payload, "load_session": True}
            )
        if action == "CALIBRATE_MAP":
            return SceneTransition(SceneId.CALIBRATE_MAP_GRID, payload={"map_file": payload})
        if action == "FORGET_MAP" and payload:
            self.context.map_config_manager.forget_map(payload)
            self.on_enter()  # Rebuild menu
        elif action == "SCAN_FOR_MAPS":
            patterns = self.context.app_config.map_search_patterns
            if patterns:
                self.context.map_config_manager.scan_for_maps(patterns)
                self.on_enter()  # Rebuild menu
        elif action == MenuActions.CALIBRATE_SCALE:
            return SceneTransition(SceneId.CALIBRATE_PPI)
        elif action == MenuActions.CALIBRATE:
            return SceneTransition(SceneId.CALIBRATE_INTRINSICS)
        elif action == MenuActions.CALIBRATE_FLASH:
            return SceneTransition(SceneId.CALIBRATE_FLASH)
        elif action == MenuActions.SET_MAP_SCALE:
            return SceneTransition(SceneId.CALIBRATE_MAP_GRID)
        elif action == MenuActions.SCAN_SESSION:
            # The context holds the SVG loader, which indicates a loaded map
            if self.context.map_system.is_map_loaded():
                return SceneTransition(SceneId.SCANNING)

            self.context.notifications.add_notification("Load a map before scanning.")
        elif action == MenuActions.EXIT:
            sys.exit(0)
        # --- Actions that modify state but don't transition ---
        elif action == MenuActions.TOGGLE_DEBUG_MODE:
            self.context.debug_mode = not self.context.debug_mode
        elif action == MenuActions.ROTATE_CW:
            self.context.map_system.rotate(90)
        elif action == MenuActions.ROTATE_CCW:
            self.context.map_system.rotate(-90)
        elif action == MenuActions.RESET_VIEW:
            self.context.map_system.reset_view_to_base()
        elif action == MenuActions.RESET_ZOOM:
            self.context.map_system.reset_zoom_to_base()

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        # Menu is always rendered on a black background, hiding the map
        return self.context.renderer.render(
            self._menu_state, background=None, map_opacity=0.0
        )
