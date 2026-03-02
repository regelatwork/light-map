from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import light_map.menu_config as config_vars
from light_map.core.map_interaction import MapInteractionController
from light_map.core.scene import Scene, SceneTransition
from light_map.gestures import GestureType
from light_map.common_types import SceneId

from light_map.map_system import MapSystem

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


class ScreenCenteredMapAdapter:
    """Adapts MapSystem to force zoom operations to pivot around screen center."""

    def __init__(self, map_system: MapSystem):
        self.map_system = map_system

    def pan(self, dx: float, dy: float) -> None:
        self.map_system.pan(dx, dy)

    def zoom_pinned(self, factor: float, center_point: Tuple[int, int]) -> None:
        # Ignore the gesture center, use screen center
        cx = self.map_system.width / 2
        cy = self.map_system.height / 2
        self.map_system.zoom_pinned(factor, (cx, cy))


class ViewingScene(Scene):
    """Handles the read-only map view."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.summon_gesture_start_time = 0.0
        self.last_token_toggle_time = 0.0

    def on_enter(self, payload: dict | None = None) -> None:
        self.summon_gesture_start_time = 0.0
        self.last_token_toggle_time = 0.0

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """In Viewing mode, we only check for the gesture to summon the menu."""
        if not inputs:
            self.summon_gesture_start_time = 0.0
            return None

        primary_gesture = inputs[0].gesture

        # Toggle token visibility
        if primary_gesture == GestureType.SHAKA:
            if self.last_token_toggle_time == 0.0 or (
                current_time - self.last_token_toggle_time > 1.0
            ):
                self.context.show_tokens = not self.context.show_tokens
                self.last_token_toggle_time = current_time

        if primary_gesture == config_vars.SUMMON_GESTURE:
            if self.summon_gesture_start_time == 0:
                self.summon_gesture_start_time = current_time
            elif (
                current_time - self.summon_gesture_start_time > config_vars.SUMMON_TIME
            ):
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the map with full opacity."""
        # This scene doesn't render anything on its own, it relies on the
        # main app loop to render the map from the context.
        # We return the frame unmodified.
        return frame


class MapScene(Scene):
    """Handles map interaction (pan and zoom)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.interaction_controller = MapInteractionController()
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False
        self.last_token_toggle_time = 0.0

    def on_enter(self, payload: dict | None = None) -> None:
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False
        self.last_token_toggle_time = 0.0
        self.context.notifications.add_notification(
            "Map Interaction Mode: Pan (1 hand), Zoom (2 hands)"
        )

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """Processes gestures for map interaction and menu summoning."""
        # Check for menu summon first
        primary_gesture = inputs[0].gesture if inputs else GestureType.NONE

        # Toggle token visibility
        if primary_gesture == GestureType.SHAKA:
            if self.last_token_toggle_time == 0.0 or (
                current_time - self.last_token_toggle_time > 1.0
            ):
                self.context.show_tokens = not self.context.show_tokens
                self.last_token_toggle_time = current_time

        if primary_gesture == config_vars.SUMMON_GESTURE:
            if self.summon_gesture_start_time == 0:
                self.summon_gesture_start_time = current_time
            elif (
                current_time - self.summon_gesture_start_time > config_vars.SUMMON_TIME
            ):
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

        # Process map interactions
        # Calculate screen-space grid size for panning snap
        grid_size = None
        map_system = self.context.map_system
        svg_loader = getattr(map_system, "svg_loader", None)
        if svg_loader:
            import os

            filename = svg_loader.filename
            entry = self.context.map_config_manager.data.maps.get(
                os.path.abspath(filename)
            )
            if entry and entry.grid_spacing_svg > 0:
                grid_size = entry.grid_spacing_svg * map_system.state.zoom

        # Use adapter to force zoom around screen center
        adapter = ScreenCenteredMapAdapter(map_system)
        was_interacting = self.is_interacting
        self.is_interacting = self.interaction_controller.process_gestures(
            inputs, adapter, grid_size=grid_size
        )

        # Save session when interaction ends
        if was_interacting and not self.is_interacting:
            map_system = self.context.map_system
            if map_system.svg_loader:
                # Use SessionManager directly to save both viewport and tokens
                from light_map.session_manager import SessionManager
                from light_map.common_types import SessionData, ViewportState
                import os

                map_file = map_system.svg_loader.filename
                session_dir = None
                if self.context.app_config.storage_manager:
                    session_dir = os.path.join(
                        self.context.app_config.storage_manager.get_data_dir(),
                        "sessions",
                    )

                session = SessionData(
                    map_file=map_file,
                    viewport=ViewportState(
                        x=map_system.state.x,
                        y=map_system.state.y,
                        zoom=map_system.state.zoom,
                        rotation=map_system.state.rotation,
                    ),
                    tokens=map_system.ghost_tokens,
                )
                SessionManager.save_for_map(map_file, session, session_dir=session_dir)

                # Also update the global last_used_map and viewport in config
                self.context.map_config_manager.save_map_viewport(
                    map_file,
                    map_system.state.x,
                    map_system.state.y,
                    map_system.state.zoom,
                    map_system.state.rotation,
                )

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the map, relying on the main loop to handle opacity based on is_interacting."""
        # Like ViewingScene, rendering is handled by the main app loop.
        # The is_interacting flag will be read by the main loop to set opacity.
        return frame
