from __future__ import annotations
import cv2
import math
import numpy as np
from typing import List, TYPE_CHECKING

from light_map.display_utils import draw_dashed_circle

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


class OverlayRenderer:
    """Handles rendering of global UI overlays (tokens, debug info, notifications)."""

    def __init__(self, context: AppContext):
        self.context = context

    def draw_ghost_tokens(self, image: np.ndarray, time_provider):
        ppi = self.context.map_config_manager.get_ppi()
        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        map_file = map_system.svg_loader.filename if map_system.svg_loader else None

        for t in map_system.ghost_tokens:
            sx, sy = map_system.world_to_screen(t.world_x, t.world_y)

            # Resolve properties for display
            resolved = map_config.resolve_token_profile(t.id, map_file)

            # Radius based on size (1 grid cell = 1 inch = ppi pixels)
            radius = int(ppi * resolved.size / 2) if ppi > 0 else 30

            # Draw circle
            color = (255, 255, 0)  # Cyan/Yellow
            if t.is_duplicate:
                color = (0, 0, 255)  # Red for duplicates
            elif not resolved.is_known:
                color = (200, 200, 200)  # Gray for unknown
            elif resolved.type == "PC":
                color = (0, 255, 0)  # Green for players
            elif resolved.type == "NPC":
                color = (0, 0, 255)  # Red for NPCs

            if t.is_occluded:
                # Pulse brightness
                pulse = (math.sin(time_provider() * 10) + 1) / 2
                alpha_pulse = 0.2 + 0.8 * pulse
                color = tuple(int(c * alpha_pulse) for c in color)

            if t.is_duplicate:
                draw_dashed_circle(image, (int(sx), int(sy)), radius, color, 2)
                cv2.putText(
                    image,
                    "DUPLICATE",
                    (int(sx) - radius, int(sy) + radius + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )
            elif not resolved.is_known:
                draw_dashed_circle(image, (int(sx), int(sy)), radius, color, 2)
                # Draw "?" in the center
                cv2.putText(
                    image,
                    "?",
                    (int(sx) - 8, int(sy) + 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color,
                    2,
                )
            else:
                cv2.circle(image, (int(sx), int(sy)), radius, color, 2)

            # Draw name
            cv2.putText(
                image,
                resolved.name,
                (int(sx) - radius, int(sy) + radius + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

    def draw_debug_overlay(
        self,
        image: np.ndarray,
        fps: float,
        current_scene_name: str,
        inputs: List[HandInput],
    ):
        cv2.putText(
            image,
            f"FPS: {int(fps)} | Scene: {current_scene_name}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        for hand_input in inputs:
            px, py = hand_input.proj_pos
            label = hand_input.gesture.name
            cv2.putText(
                image,
                label,
                (px, py - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
            cv2.circle(image, (px, py), 10, (0, 255, 255), -1)

    def draw_notifications(self, image: np.ndarray):
        for i, msg in enumerate(self.context.notifications.get_active_notifications()):
            cv2.putText(
                image,
                msg,
                (50, 100 + i * 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
