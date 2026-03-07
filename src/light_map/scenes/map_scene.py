from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import light_map.menu_config as config_vars
from light_map.core.map_interaction import MapInteractionController
from light_map.core.scene import Scene, SceneTransition
from light_map.gestures import GestureType
from light_map.common_types import SceneId
from light_map.dwell_tracker import DwellTracker

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


class BaseMapScene(Scene):
    """Base class for scenes that interact with the map (Viewing, Interaction)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.summon_gesture_start_time = 0.0
        self.last_token_toggle_time = 0.0
        self.last_update_time = 0.0
        self.inspection_end_time = 0.0
        ppi = getattr(self.context.app_config, "projector_ppi", 96.0)
        self.dwell_tracker = DwellTracker(
            radius_pixels=ppi * 0.5, dwell_time_threshold=2.0
        )

    def _handle_dwell_trigger(self, cursor_pos: Tuple[int, int]):
        """Detects if we are pointing at a token or a door."""
        world_x, world_y = self.context.map_system.screen_to_world(
            cursor_pos[0], cursor_pos[1]
        )

        # 1. Check Tokens
        for token in self.context.raw_tokens:
            dist = np.sqrt(
                (token.world_x - world_x) ** 2 + (token.world_y - world_y) ** 2
            )
            # Use 0.5 grid cell radius for selection
            grid_spacing = self.context.map_config_manager.get_map_grid_spacing(
                self.context.map_system.svg_loader.filename
            )
            if dist < 0.5 * grid_spacing:
                self.context.inspected_token_id = token.id
                # Resolve token name for better notification
                map_file = (
                    self.context.map_system.svg_loader.filename
                    if self.context.map_system.svg_loader
                    else None
                )
                resolved = self.context.map_config_manager.resolve_token_profile(
                    token.id, map_file
                )
                self.context.notifications.add_notification(
                    f"Inspecting: {resolved.name}", duration=0.5
                )

                # --- NEW: Calculate LOS mask for inspection on-demand ---
                if (
                    self.context.visibility_engine
                    and self.context.map_system.is_map_loaded()
                ):
                    engine = self.context.visibility_engine
                    mask_w = engine.width
                    mask_h = engine.height

                    token_mask = engine.get_token_vision_mask(
                        token.id,
                        token.world_x,
                        token.world_y,
                        size=resolved.size,
                        vision_range_grid=25.0,
                        mask_width=mask_w,
                        mask_height=mask_h,
                    )
                    self.context.inspected_token_mask = token_mask

                return

        # 2. Check Doors
        door_layer = self._check_door_collision(world_x, world_y)
        if door_layer:
            self.context.selected_door = door_layer
            self.context.notifications.add_notification(
                f"Selected Door: {door_layer}", duration=0.5
            )
            return

    def _check_door_collision(self, wx: float, wy: float) -> Optional[str]:
        """Checks if world coordinate (wx, wy) is near any door segment."""
        if not self.context.map_system.svg_loader:
            return None

        blockers = self.context.map_system.svg_loader.get_visibility_blockers()
        # Radius for selection (e.g. 0.3 grid cells)
        grid_spacing = self.context.map_config_manager.get_map_grid_spacing(
            self.context.map_system.svg_loader.filename
        )
        threshold = 0.3 * grid_spacing

        for blocker in blockers:
            if blocker.type != "door":
                continue

            # Check proximity to any segment
            pts = blocker.segments
            for i in range(len(pts) - 1):
                p1 = pts[i]
                p2 = pts[i + 1]

                # Distance from point to segment
                d = self._point_to_segment_dist((wx, wy), p1, p2)
                if d < threshold:
                    return blocker.layer_name
        return None

    def _point_to_segment_dist(self, p, s1, s2):
        px, py = p
        x1, y1 = s1
        x2, y2 = s2
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return np.sqrt((px - x1) ** 2 + (py - y1) ** 2)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))

        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return np.sqrt((px - closest_x) ** 2 + (py - closest_y) ** 2)

    def _update_dwell_and_linger(
        self,
        primary_gesture: GestureType,
        cursor_pos: Optional[Tuple[int, int]],
        dt: float,
        current_time: float,
    ) -> None:
        """Centralized logic for dwell triggering and inspection linger."""
        if primary_gesture == GestureType.POINTING and cursor_pos is not None:
            if self.dwell_tracker.update(cursor_pos, dt):
                self._handle_dwell_trigger(cursor_pos)
                self.inspection_end_time = 0.0  # Reset while actively pointing
        else:
            self.dwell_tracker.reset()

            # Start linger timer if we were inspecting
            if (
                self.context.inspected_token_id is not None
                and self.inspection_end_time == 0.0
            ):
                duration = getattr(
                    self.context.app_config, "inspection_linger_duration", 10.0
                )
                self.inspection_end_time = current_time + duration

            # Clear inspection if linger expired
            if (
                self.inspection_end_time > 0
                and current_time >= self.inspection_end_time
            ):
                self.context.inspected_token_id = None
                self.inspection_end_time = 0.0


class ViewingScene(BaseMapScene):
    """Handles the read-only map view."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.is_dirty = True  # Start dirty to render once

    def on_enter(self, payload: dict | None = None) -> None:
        self.summon_gesture_start_time = 0.0
        self.last_token_toggle_time = 0.0
        self.is_dirty = True
        self.dwell_tracker.reset()

    @property
    def blocking(self) -> bool:
        """Viewing scene should show the map."""
        return False

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """In Viewing mode, we only check for the gesture to summon the menu."""
        dt = (
            current_time - self.last_update_time if self.last_update_time > 0 else 0.033
        )
        self.last_update_time = current_time

        if not inputs:
            self.summon_gesture_start_time = 0.0
            self._update_dwell_and_linger(GestureType.NONE, None, dt, current_time)
            return None

        primary_gesture = inputs[0].gesture
        px, py = inputs[0].proj_pos
        ux, uy = inputs[0].unit_direction

        # Calculate 1-inch virtual pointer offset if pointing
        ppi = getattr(self.context.app_config, "projector_ppi", 96.0)
        cursor_pos = (int(px + ux * ppi), int(py + uy * ppi))

        # --- DWELL AND LINGER ---
        self._update_dwell_and_linger(primary_gesture, cursor_pos, dt, current_time)

        # Toggle token visibility
        if primary_gesture == GestureType.SHAKA:
            if self.last_token_toggle_time == 0.0 or (
                current_time - self.last_token_toggle_time > 1.0
            ):
                self.context.show_tokens = not self.context.show_tokens
                self.last_token_toggle_time = current_time

        if primary_gesture == config_vars.SUMMON_GESTURE:
            if self.summon_gesture_start_time == 0:
                logging.debug("Summon gesture started")
                self.summon_gesture_start_time = current_time
            elif (
                current_time - self.summon_gesture_start_time > config_vars.SUMMON_TIME
            ):
                logging.info("Summon gesture triggered transition to MENU")
                self.summon_gesture_start_time = 0.0
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame


class MapScene(BaseMapScene):
    """Handles map interaction (pan and zoom)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.interaction_controller = MapInteractionController()
        self.is_interacting = False
        self.is_dirty = True

    def on_enter(self, payload: dict | None = None) -> None:
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False
        self.last_token_toggle_time = 0.0
        self.is_dirty = True
        self.dwell_tracker.reset()
        self.context.notifications.add_notification(
            "Map Interaction Mode: Pan (1 hand), Zoom (2 hands)"
        )

    @property
    def blocking(self) -> bool:
        """Map interaction scene should show the map."""
        return False

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """Processes gestures for map interaction and menu summoning."""
        dt = (
            current_time - self.last_update_time if self.last_update_time > 0 else 0.033
        )
        self.last_update_time = current_time

        primary_gesture = inputs[0].gesture if inputs else GestureType.NONE
        cursor_pos = None
        if inputs:
            px, py = inputs[0].proj_pos
            ux, uy = inputs[0].unit_direction
            ppi = getattr(self.context.app_config, "projector_ppi", 96.0)
            cursor_pos = (int(px + ux * ppi), int(py + uy * ppi))

        # --- DWELL AND LINGER ---
        self._update_dwell_and_linger(primary_gesture, cursor_pos, dt, current_time)

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
                self.summon_gesture_start_time = 0.0
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

        # Process map interactions
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

        adapter = ScreenCenteredMapAdapter(map_system)
        was_interacting = self.is_interacting
        self.is_interacting = self.interaction_controller.process_gestures(
            inputs, adapter, grid_size=grid_size
        )

        if was_interacting and not self.is_interacting:
            if self.context.save_session:
                self.context.save_session()

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame
