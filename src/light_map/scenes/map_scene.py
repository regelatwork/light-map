from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

import light_map.menu_config as config_vars
from light_map.core.map_interaction import MapInteractionController
from light_map.core.scene import Scene, SceneTransition
from light_map.gestures import GestureType
from light_map.common_types import SceneId, SelectionType, TimerKey, Action
from light_map.dwell_tracker import DwellTracker

from light_map.map_system import MapSystem, MapState

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
        self.last_update_time = 0.0
        ppi = getattr(self.context.app_config, "projector_ppi", 96.0)
        self.dwell_tracker = DwellTracker(
            radius_pixels=ppi * 0.5,
            dwell_time_threshold=2.0,
            events=self.context.events,
        )

    def _handle_dwell_trigger(self, cursor_pos: Tuple[int, int]):
        """Detects if we are pointing at a token or a door."""
        world_x, world_y = self.context.map_system.screen_to_world(
            cursor_pos[0], cursor_pos[1]
        )

        # Combine physical and logical tokens for inspection check
        # logical 'tokens' take precedence if they have the same ID?
        # Actually, let's just combine them and iterate.
        all_candidate_tokens = []
        if self.context.state:
            all_candidate_tokens.extend(self.context.state.tokens)

        # Add raw tokens, avoiding duplicates if possible (simple ID check)
        existing_ids = {t.id for t in all_candidate_tokens}
        for rt in self.context.raw_tokens:
            if rt.id not in existing_ids:
                all_candidate_tokens.append(rt)

        # 1. Check Tokens
        for token in all_candidate_tokens:
            dist = np.sqrt(
                (token.world_x - world_x) ** 2 + (token.world_y - world_y) ** 2
            )
            # Use 0.5 grid cell radius for selection
            grid_spacing = self.context.map_config_manager.get_map_grid_spacing(
                self.context.map_system.svg_loader.filename
            )
            if dist < 0.5 * grid_spacing:
                self.context.inspected_token_id = token.id
                if self.context.state:
                    self.context.state.selection.type = SelectionType.TOKEN
                    self.context.state.selection.id = str(token.id)

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
                    f"Inspecting: {resolved.name}", duration=2.0
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
        door_id = self._check_door_collision(world_x, world_y)
        if door_id:
            self.context.selected_door = door_id
            if self.context.state:
                self.context.state.selection.type = SelectionType.DOOR
                self.context.state.selection.id = door_id

            self.context.notifications.add_notification(
                f"Selected Door: {door_id}", duration=2.0
            )
            return

    def _check_door_collision(self, wx: float, wy: float) -> Optional[str]:
        """Checks if world coordinate (wx, wy) is near any door segment."""
        if not self.context.map_system.svg_loader:
            return None

        blockers = self.context.map_system.svg_loader.get_visibility_blockers()
        # Radius for selection (e.g. 0.5 grid cells)
        grid_spacing = self.context.map_config_manager.get_map_grid_spacing(
            self.context.map_system.svg_loader.filename
        )
        threshold = max(0.5 * grid_spacing, 10.0)

        from light_map.visibility_types import VisibilityType

        for blocker in blockers:
            if blocker.type != VisibilityType.DOOR:
                continue

            # Check proximity to any segment
            pts = blocker.segments
            for i in range(len(pts) - 1):
                p1 = pts[i]
                p2 = pts[i + 1]

                # Distance from point to segment
                d = self._point_to_segment_dist((wx, wy), p1, p2)
                if d < threshold:
                    return blocker.id
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

    def _find_target_at_point(self, cursor_pos: Tuple[int, int]) -> Optional[str]:
        """Finds the ID of a token or door at the given screen point."""
        world_x, world_y = self.context.map_system.screen_to_world(
            cursor_pos[0], cursor_pos[1]
        )

        # 1. Check Tokens
        all_candidate_tokens = []
        if self.context.state:
            all_candidate_tokens.extend(self.context.state.tokens)

        existing_ids = {t.id for t in all_candidate_tokens}
        for rt in self.context.raw_tokens:
            if rt.id not in existing_ids:
                all_candidate_tokens.append(rt)

        map_file = (
            self.context.map_system.svg_loader.filename
            if self.context.map_system.svg_loader
            else None
        )
        grid_spacing = self.context.map_config_manager.get_map_grid_spacing(map_file)
        threshold = max(
            0.5 * grid_spacing, 10.0
        )  # Ensure at least 10 units for new maps

        for token in all_candidate_tokens:
            dist = np.sqrt(
                (token.world_x - world_x) ** 2 + (token.world_y - world_y) ** 2
            )
            if dist < threshold:
                return str(token.id)

        # 2. Check Doors
        door_id = self._check_door_collision(world_x, world_y)
        if door_id:
            return door_id

        return None

    def _update_dwell_and_linger(
        self,
        primary_gesture: GestureType,
        cursor_pos: Optional[Tuple[int, int]],
        dt: float,
        current_time: float,
    ) -> bool:
        """Centralized logic for dwell triggering and inspection linger."""
        if primary_gesture == GestureType.POINTING and cursor_pos is not None:
            target_id = self._find_target_at_point(cursor_pos)
            # Check if dwell triggered (handles both polling and event-based triggers)
            if self.dwell_tracker.update(cursor_pos, dt, target_id=target_id):
                return True
        else:
            self.dwell_tracker.reset()

            # Start linger timer if we were inspecting
            if (
                self.context.inspected_token_id is not None
                and not self.context.events.has_event(TimerKey.INSPECTION_LINGER)
            ):
                duration = getattr(
                    self.context.app_config, "inspection_linger_duration", 10.0
                )
                self.context.events.schedule(
                    duration,
                    lambda: Action.CLEAR_INSPECTION,
                    key=TimerKey.INSPECTION_LINGER,
                )
        return False


class ViewingScene(BaseMapScene):
    """Handles the read-only map view."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.mark_dirty()  # Start dirty to render once

    def on_enter(self, payload: dict | None = None) -> None:
        self.mark_dirty()
        self.dwell_tracker.reset()

    @property
    def blocking(self) -> bool:
        """Viewing scene should show the map."""
        return False

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        """In Viewing mode, we only check for the gesture to summon the menu."""
        if Action.TRIGGER_MENU in actions:
            return SceneTransition(SceneId.MENU)

        if Action.TOGGLE_TOKEN_VISIBILITY in actions:
            self.context.show_tokens = not self.context.show_tokens

        if Action.CLEAR_INSPECTION in actions:
            self.context.inspected_token_id = None

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
        dwell_just_triggered = self._update_dwell_and_linger(
            primary_gesture, cursor_pos, dt, current_time
        )

        if (dwell_just_triggered or Action.DWELL_TRIGGER in actions) and cursor_pos:
            self._handle_dwell_trigger(cursor_pos)
            self.context.events.cancel(TimerKey.INSPECTION_LINGER)

        # Toggle token visibility (using Action trigger)
        if primary_gesture == GestureType.SHAKA:
            if not self.context.events.has_event(TimerKey.TOKEN_TOGGLE_COOLDOWN):
                self.context.events.schedule(
                    1.0,
                    lambda: Action.TOGGLE_TOKEN_VISIBILITY,
                    key=TimerKey.TOKEN_TOGGLE_COOLDOWN,
                )

        if primary_gesture == config_vars.SUMMON_GESTURE:
            if not self.context.events.has_event(TimerKey.SUMMON_MENU):
                logging.debug("Summon gesture started")
                self.context.events.schedule(
                    config_vars.SUMMON_TIME,
                    lambda: Action.TRIGGER_MENU,
                    key=TimerKey.SUMMON_MENU,
                )
        else:
            if self.context.events.has_event(TimerKey.SUMMON_MENU):
                self.context.events.cancel(TimerKey.SUMMON_MENU)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame


class MapScene(BaseMapScene):
    """Handles map interaction (pan and zoom)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.interaction_controller = MapInteractionController()
        self.is_interacting = False
        self.pre_interaction_state = None
        self.mark_dirty()

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False
        self.pre_interaction_state = None
        self.mark_dirty()
        self.dwell_tracker.reset()
        self.context.notifications.add_notification(
            "Map Interaction Mode: Pan (1 hand), Zoom (2 hands)"
        )

    @property
    def blocking(self) -> bool:
        """Map interaction scene should show the map."""
        return False

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        """Processes gestures for map interaction and menu summoning."""
        if Action.TRIGGER_MENU in actions:
            return SceneTransition(SceneId.MENU)

        if Action.TOGGLE_TOKEN_VISIBILITY in actions:
            self.context.show_tokens = not self.context.show_tokens

        if Action.CLEAR_INSPECTION in actions:
            self.context.inspected_token_id = None

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
        dwell_just_triggered = self._update_dwell_and_linger(
            primary_gesture, cursor_pos, dt, current_time
        )

        if (dwell_just_triggered or Action.DWELL_TRIGGER in actions) and cursor_pos:
            self._handle_dwell_trigger(cursor_pos)
            self.context.events.cancel(TimerKey.INSPECTION_LINGER)

        # Toggle token visibility (using Action trigger)
        if primary_gesture == GestureType.SHAKA:
            if not self.context.events.has_event(TimerKey.TOKEN_TOGGLE_COOLDOWN):
                self.context.events.schedule(
                    1.0,
                    lambda: Action.TOGGLE_TOKEN_VISIBILITY,
                    key=TimerKey.TOKEN_TOGGLE_COOLDOWN,
                )

        if primary_gesture == config_vars.SUMMON_GESTURE:
            if not self.context.events.has_event(TimerKey.SUMMON_MENU):
                self.context.events.schedule(
                    config_vars.SUMMON_TIME,
                    lambda: Action.TRIGGER_MENU,
                    key=TimerKey.SUMMON_MENU,
                )
        else:
            if self.context.events.has_event(TimerKey.SUMMON_MENU):
                self.context.events.cancel(TimerKey.SUMMON_MENU)

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

        # Save potential pre-interaction state
        temp_pre_state = None
        if not was_interacting:
            import copy

            temp_pre_state = copy.deepcopy(map_system.state)

        self.is_interacting = self.interaction_controller.process_gestures(
            inputs, adapter, grid_size=grid_size
        )

        if not was_interacting and self.is_interacting:
            self.pre_interaction_state = temp_pre_state

        if was_interacting and not self.is_interacting:
            if self.pre_interaction_state and (
                self.pre_interaction_state.x != map_system.state.x
                or self.pre_interaction_state.y != map_system.state.y
                or self.pre_interaction_state.zoom != map_system.state.zoom
                or self.pre_interaction_state.rotation != map_system.state.rotation
            ):
                # We save the state that was there BEFORE the interaction.
                # So when we undo, we go back to it.
                map_system.undo_stack.append(self.pre_interaction_state)
                if len(map_system.undo_stack) > map_system.max_stack_size:
                    map_system.undo_stack.pop(0)
                map_system.redo_stack.clear()

            if self.context.save_session:
                self.context.save_session()

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame
