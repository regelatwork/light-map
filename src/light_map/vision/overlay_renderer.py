from __future__ import annotations
import cv2
import math
import numpy as np
from typing import List, TYPE_CHECKING

from light_map.display_utils import draw_dashed_circle, draw_text_with_background
from light_map.common_types import ImagePatch

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


class OverlayRenderer:
    """Handles rendering of global UI overlays (tokens, debug info, notifications)."""

    def __init__(self, context: AppContext):
        self.context = context

    def _create_patch_from_buffer(
        self, buffer: np.ndarray, x: int, y: int
    ) -> ImagePatch:
        """Helper to convert a BGR buffer into a BGRA patch with transparency heuristic."""
        h, w = buffer.shape[:2]
        patch_data = np.zeros((h, w, 4), dtype=np.uint8)
        patch_data[:, :, :3] = buffer

        # Heuristic: any pixel > 0 is visible
        mask = np.any(buffer > 0, axis=2)
        patch_data[mask, 3] = 255

        return ImagePatch(x=x, y=y, width=w, height=h, data=patch_data)

    def draw_ghost_tokens(self, time_provider) -> List[ImagePatch]:
        patches = []
        ppi = self.context.map_config_manager.get_ppi()
        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        map_file = map_system.svg_loader.filename if map_system.svg_loader else None

        for t in map_system.ghost_tokens:
            sx, sy = map_system.world_to_screen(t.world_x, t.world_y)
            resolved = map_config.resolve_token_profile(t.id, map_file)
            radius = int(ppi) if ppi > 0 else 30

            # Define local area for this token
            # Padding to account for name text below the token
            padding = 100
            x1, y1 = int(sx - radius - 10), int(sy - radius - 10)
            x2, y2 = int(sx + radius + 10), int(sy + radius + padding)

            w, h = x2 - x1, y2 - y1
            if w <= 0 or h <= 0:
                continue

            token_buffer = np.zeros((h, w, 3), dtype=np.uint8)
            # Local coordinates
            lsx, lsy = int(sx) - x1, int(sy) - y1

            # Resolve color
            color = (255, 255, 0)
            if t.is_duplicate:
                color = (0, 0, 255)
            elif not resolved.is_known:
                color = (200, 200, 200)
            elif resolved.type == "PC":
                color = (0, 255, 0)
            elif resolved.type == "NPC":
                color = (0, 0, 255)

            if t.is_occluded:
                pulse = (math.sin(time_provider() * 10) + 1) / 2
                alpha_pulse = 0.2 + 0.8 * pulse
                color = tuple(int(c * alpha_pulse) for c in color)

            if t.is_duplicate:
                draw_dashed_circle(token_buffer, (lsx, lsy), radius, color, 2)
                draw_text_with_background(
                    token_buffer,
                    "DUPLICATE",
                    (lsx - radius, lsy + radius + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )
            elif not resolved.is_known:
                draw_dashed_circle(token_buffer, (lsx, lsy), radius, color, 2)
                cv2.putText(
                    token_buffer,
                    "?",
                    (lsx - 8, lsy + 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color,
                    2,
                )
            else:
                cv2.circle(token_buffer, (lsx, lsy), radius, color, 2)

            draw_text_with_background(
                token_buffer,
                resolved.name,
                (lsx - radius, lsy + radius + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

            patches.append(self._create_patch_from_buffer(token_buffer, x1, y1))

        return patches

    def draw_debug_overlay(
        self,
        fps: float,
        current_scene_name: str,
        inputs: List[HandInput],
    ) -> List[ImagePatch]:
        patches = []

        # 1. Main Debug info (Top Left)
        text = f"FPS: {int(fps)} | Scene: {current_scene_name}"
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        debug_w, debug_h = tw + 20, th + baseline + 20
        debug_buffer = np.zeros((debug_h, debug_w, 3), dtype=np.uint8)
        draw_text_with_background(
            debug_buffer,
            text,
            (10, th + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        patches.append(self._create_patch_from_buffer(debug_buffer, 50, 40))

        # 2. Hand inputs
        for hand_input in inputs:
            px, py = hand_input.proj_pos
            label = hand_input.gesture.name

            (lw, lh), lb = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
            hand_w, hand_h = max(lw + 20, 40), lh + lb + 60
            hand_buffer = np.zeros((hand_h, hand_w, 3), dtype=np.uint8)

            # Local draw
            lx, ly = hand_w // 2, hand_h - 10
            draw_text_with_background(
                hand_buffer,
                label,
                (10, lh + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
            cv2.circle(hand_buffer, (lx, ly), 10, (0, 255, 255), -1)

            patches.append(
                self._create_patch_from_buffer(
                    hand_buffer, px - hand_w // 2, py - hand_h + 10
                )
            )

        return patches

    def draw_notifications(self) -> List[ImagePatch]:
        patches = []
        notifications = self.context.notifications.get_active_notifications()
        if not notifications:
            return []

        # For simplicity, render all active notifications in one patch
        # starting at fixed position
        max_w = 0
        for msg in notifications:
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
            max_w = max(max_w, tw + 20)

        h_per_msg = 40
        total_h = len(notifications) * h_per_msg + 20
        buffer = np.zeros((total_h, max_w, 3), dtype=np.uint8)

        for i, msg in enumerate(notifications):
            draw_text_with_background(
                buffer,
                msg,
                (10, 30 + i * h_per_msg),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )

        patches.append(self._create_patch_from_buffer(buffer, 50, 100))
        return patches
