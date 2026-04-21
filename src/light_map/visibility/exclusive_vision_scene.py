from __future__ import annotations
import logging
from typing import TYPE_CHECKING, List, Optional

import numpy as np
from light_map.core.scene import SceneTransition
from light_map.core.common_types import (
    SceneId,
    Action,
    TimerKey,
    MapRenderState,
)
from light_map.input.gestures import GestureType
from light_map.map.map_scene import BaseMapScene

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput
    from light_map.core.common_types import Layer


class ExclusiveVisionScene(BaseMapScene):
    """
    Tactical mode that displays the line-of-sight from a single token's perspective.
    Everything outside the token's vision is blacked out.
    """

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.token_id: Optional[int] = None
        self.last_update_time = 0.0

    def on_enter(self, payload: dict | None = None) -> None:
        if payload and "token_id" in payload:
            self.token_id = payload["token_id"]
            self.context.inspected_token_id = self.token_id
            if self.context.state:
                self.context.state.inspected_token_id = self.token_id
                # Reset bonuses on entry to ensure fresh calculation from new perspective
                self.context.state.tactical_bonuses = {}

        # Ensure map is full brightness during inspection
        self.context.layer_manager.map_layer.opacity = 1.0
        if self.context.state:
            current = self.context.state.map_render_state
            self.context.state.map_render_state = MapRenderState(
                opacity=1.0, quality=current.quality, filepath=current.filepath
            )

        self.dwell_tracker.reset()
        logging.info(f"Entered ExclusiveVisionScene for token {self.token_id}")

    def on_exit(self) -> None:
        self.context.inspected_token_id = None
        self.context.inspected_token_mask = None
        if self.context.state:
            self.context.state.inspected_token_id = None
            self.context.state.inspected_token_mask = None
            self.context.state.tactical_bonuses = {}
        self.context.events.cancel(TimerKey.INSPECTION_LINGER)
        logging.info("Exited ExclusiveVisionScene")

    def get_active_layers(self, app: AppContext) -> List[Layer]:
        """
        Returns the layer stack for exclusive vision.
        Injects the ExclusiveVisionLayer above visibility/fow.
        """
        lm = self.context.layer_manager

        # Base stack
        stack = [
            lm.map_layer,
            lm.door_layer,
            lm.fow_layer,
            lm.visibility_layer,
        ]

        # Insert ExclusiveVisionLayer if we have a mask
        mask = self.context.inspected_token_mask
        if self.context.state and self.context.state.inspected_token_mask is not None:
            mask = self.context.state.inspected_token_mask

        if mask is not None:
            lm.exclusive_vision_layer.set_mask(mask)
            stack.append(lm.exclusive_vision_layer)

        stack.extend(
            [
                lm.aruco_mask_layer,
                lm.hand_mask_layer,
                lm.token_layer,
                lm.tactical_overlay_layer,
                lm.menu_layer,
                lm.notification_layer,
                lm.debug_layer,
                lm.selection_progress_layer,
                lm.cursor_layer,
            ]
        )
        return stack

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        # ALWAYS update mask and tactical bonuses
        self._update_inspection_mask()

        if Action.TRIGGER_MENU in actions:
            return SceneTransition(SceneId.MENU)

        if Action.CLEAR_INSPECTION in actions:
            return SceneTransition(SceneId.VIEWING)

        dt = (
            current_time - self.last_update_time if self.last_update_time > 0 else 0.033
        )
        self.last_update_time = current_time

        if not inputs:
            self._handle_no_input(dt)
            return None

        primary_gesture = inputs[0].gesture
        px, py = inputs[0].proj_pos
        ux, uy = inputs[0].unit_direction
        ppi = getattr(self.context.app_config, "projector_ppi", 96.0)
        cursor_pos = (int(px + ux * ppi), int(py + uy * ppi))

        # Update dwell tracker to allow switching to another token
        dwell_triggered = self.dwell_tracker.update(cursor_pos, dt)
        if dwell_triggered or Action.DWELL_TRIGGER in actions:
            # Check if we are pointing at a NEW token
            self._handle_dwell_trigger(cursor_pos)
            if self.context.inspected_token_id != self.token_id:
                self.token_id = self.context.inspected_token_id
                if self.context.state:
                    self.context.state.inspected_token_id = self.token_id

            self.context.events.cancel(TimerKey.INSPECTION_LINGER)

        # If user is pointing anywhere, cancel the linger timeout
        if primary_gesture == GestureType.POINTING:
            self.context.events.cancel(TimerKey.INSPECTION_LINGER)
        else:
            self._handle_no_input(dt)

        return None

    def _handle_no_input(self, dt: float):
        """Schedules the exit transition if no interaction is occurring."""
        if not self.context.events.has_event(TimerKey.INSPECTION_LINGER):
            duration = getattr(
                self.context.app_config, "inspection_linger_duration", 10.0
            )
            self.context.events.schedule(
                duration,
                lambda: Action.CLEAR_INSPECTION,
                key=TimerKey.INSPECTION_LINGER,
            )

    def _update_inspection_mask(self):
        """Recalculates the LOS mask for the currently inspected token."""
        if self.token_id is None or not self.context.visibility_engine:
            return

        # Find token in state or raw tokens
        target_token = None
        if self.context.state:
            for t in self.context.state.tokens:
                if t.id == self.token_id:
                    target_token = t
                    break

        if not target_token:
            for rt in self.context.raw_tokens:
                if rt.id == self.token_id:
                    target_token = rt
                    break

        if not target_token:
            return

        map_file = (
            self.context.map_system.svg_loader.filename
            if self.context.map_system.svg_loader
            else None
        )
        resolved = self.context.map_config_manager.resolve_token_profile(
            self.token_id, map_file
        )

        engine = self.context.visibility_engine
        mask_w, mask_h = engine.width, engine.height

        token_mask, _ = engine.get_token_vision_mask(
            self.token_id,
            target_token.world_x,
            target_token.world_y,
            size=resolved.size,
            vision_range_grid=25.0,
            mask_width=mask_w,
            mask_height=mask_h,
        )

        # Update both for compatibility
        self.context.inspected_token_mask = token_mask
        if self.context.state:
            self.context.state.inspected_token_mask = token_mask

        # --- TACTICAL COVER CALCULATION ---
        if self.context.state:
            old_bonuses = self.context.state.tactical_bonuses
            new_bonuses = {}
            changed = False

            # Use combined tokens list for calculation
            all_tokens = []
            all_tokens.extend(self.context.state.tokens)
            existing_ids = {t.id for t in all_tokens}
            for rt in self.context.raw_tokens:
                if rt.id not in existing_ids:
                    all_tokens.append(rt)

            # Determine profile of inspected token
            inspected_profile = self.context.map_config_manager.resolve_token_profile(
                self.token_id, map_file
            )
            is_inspected_pc = inspected_profile.type == "PC"

            for t in all_tokens:
                if t.id == self.token_id:
                    continue

                # Check profile of 'other' token
                other_profile = self.context.map_config_manager.resolve_token_profile(
                    t.id, map_file
                )
                is_other_pc = other_profile.type == "PC"

                # Tactical Rule:
                # 1. If we inspect a PC, calculate cover for all visible tokens (mostly NPCs).
                # 2. If we inspect an NPC, calculate cover ONLY for visible PCs.
                if not is_inspected_pc and not is_other_pc:
                    # logging.debug(f"[ExclusiveVision] Skipping NPC-to-NPC: {self.token_id} to {t.id}")
                    continue

                # Check if token is visible in the mask (Searchlight check)
                # World units -> Mask units
                tx = int(t.world_x * engine.svg_to_mask_scale)
                ty = int(t.world_y * engine.svg_to_mask_scale)

                is_in_searchlight = False
                if 0 <= tx < mask_w and 0 <= ty < mask_h:
                    # Check 3x3 neighborhood for robustness
                    y_start = max(0, ty - 1)
                    y_end = min(mask_h, ty + 2)
                    x_start = max(0, tx - 1)
                    x_end = min(mask_w, tx + 2)
                    if np.any(token_mask[y_start:y_end, x_start:x_end] > 0):
                        is_in_searchlight = True

                if not is_in_searchlight:
                    continue

                ac, reflex = engine.calculate_token_cover_bonuses(target_token, t)

                old_ac, old_reflex = old_bonuses.get(t.id, (0, 0))

                # If seen in searchlight, we log it (even if value is same as before,
                # but we only log if it's a NEW inspection or logical change)
                if is_in_searchlight:
                    changed = True
                    if ac != 0 or reflex != 0:
                        logging.info(
                            f"[ExclusiveVision] Cover calculated for token {t.id} ({other_profile.name}, {other_profile.type}): AC={ac}, Reflex={reflex}"
                        )
                    else:
                        logging.info(
                            f"[ExclusiveVision] LOS is clear for token {t.id} ({other_profile.name})"
                        )
                elif old_ac != 0 or old_reflex != 0:
                    changed = True
                    logging.info(
                        f"[ExclusiveVision] Cover lost for token {t.id} ({other_profile.name})"
                    )

                new_bonuses[t.id] = (ac, reflex)

            # Update state if logical content changed or population changed
            if changed or len(new_bonuses) != len(old_bonuses):
                self.context.state.tactical_bonuses = new_bonuses

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame
