from __future__ import annotations

import math
from typing import TYPE_CHECKING

import cv2
import numpy as np

from light_map.core.common_types import ImagePatch, Token
from light_map.core.display_utils import (
    draw_dashed_circle,
    draw_text_with_background,
    parse_color,
)


if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


class OverlayRenderer:
    """Handles rendering of global UI overlays (tokens, debug info, notifications)."""

    def __init__(self, context: AppContext):
        self.context = context

    def _create_patch_from_buffer(self, buffer: np.ndarray, x: int, y: int) -> ImagePatch:
        """Helper to convert a BGR buffer into a BGRA patch with transparency heuristic."""
        h, w = buffer.shape[:2]
        patch_data = np.zeros((h, w, 4), dtype=np.uint8)
        patch_data[:, :, :3] = buffer

        # Heuristic: any pixel > 0 is visible
        mask = np.any(buffer > 0, axis=2)
        patch_data[mask, 3] = 255

        return ImagePatch(x=x, y=y, width=w, height=h, data=patch_data)

    def draw_ghost_tokens(self, time_provider) -> list[ImagePatch]:
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

            # --- CHANGE: USE 4 CHANNELS ---
            token_buffer = np.zeros((h, w, 4), dtype=np.uint8)
            # Local coordinates
            lsx, lsy = int(sx) - x1, int(sy) - y1

            # Resolve color
            if resolved.color:
                color = parse_color(resolved.color)
            else:
                color = (255, 255, 0)  # Default Cyan
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

            # Draw token circle
            if t.is_duplicate:
                draw_dashed_circle(token_buffer, (lsx, lsy), radius, (*color, 255), 2)
                draw_text_with_background(
                    token_buffer,
                    "DUPLICATE",
                    (lsx - radius, lsy + radius + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (*color, 255),
                    1,
                )
            elif not resolved.is_known:
                draw_dashed_circle(token_buffer, (lsx, lsy), radius, (*color, 255), 2)
                cv2.putText(
                    token_buffer,
                    "?",
                    (lsx - 8, lsy + 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (*color, 255),
                    2,
                )
            else:
                cv2.circle(token_buffer, (lsx, lsy), radius, (*color, 255), 2)

            draw_text_with_background(
                token_buffer,
                resolved.name,
                (lsx - radius, lsy + radius + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (*color, 255),
                1,
                bg_color=(0, 0, 0),
                alpha=0.8,
            )

            patches.append(ImagePatch(x=x1, y=y1, width=w, height=h, data=token_buffer))

        return patches

    def draw_debug_overlay(
        self,
        fps: float,
        current_scene_name: str,
        inputs: list[HandInput],
        tokens: list[Token] | None = None,
    ) -> list[ImagePatch]:
        patches = []

        # 1. Main Debug info (Top Left)
        text = f"FPS: {int(fps)} | Scene: {current_scene_name}"
        if tokens:
            stereo_active = sum(1 for t in tokens if getattr(t, "is_stereo", False))
            text += f" | Tokens: {len(tokens)} (Stereo: {stereo_active}/{len(tokens)})"
        (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        debug_w, debug_h = tw + 20, th + baseline + 20
        debug_buffer = np.zeros((debug_h, debug_w, 4), dtype=np.uint8)
        draw_text_with_background(
            debug_buffer,
            text,
            (10, th + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255, 255),
            2,
        )
        patches.append(ImagePatch(x=50, y=40, width=debug_w, height=debug_h, data=debug_buffer))

        # 2. Hand inputs
        for hand_input in inputs:
            px, py = hand_input.proj_pos
            label = hand_input.gesture.name

            # Draw a small yellow dot at the physical tip (projected)
            hand_buffer = np.zeros((30, 30, 4), dtype=np.uint8)
            cv2.circle(hand_buffer, (15, 15), 5, (0, 255, 255, 255), -1)
            patches.append(ImagePatch(x=px - 15, y=py - 15, width=30, height=30, data=hand_buffer))

            # Draw label above it
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_buffer = np.zeros((lh + 10, lw + 10, 4), dtype=np.uint8)
            draw_text_with_background(
                label_buffer,
                label,
                (5, lh + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255, 255),
                1,
            )
            patches.append(
                ImagePatch(
                    x=px - lw // 2,
                    y=py - 30 - lh,
                    width=lw + 10,
                    height=lh + 10,
                    data=label_buffer,
                )
            )

        # 3. Token stereo debug indicators
        if tokens:
            map_system = self.context.map_system
            ppi = (
                self.context.map_config_manager.get_ppi()
                if self.context.map_config_manager
                else 55.0
            )
            radius = int(ppi) if ppi > 0 else 30
            ring_r = radius + 6

            for token in tokens:
                if token.screen_x is not None and token.screen_y is not None:
                    sx, sy = int(token.screen_x), int(token.screen_y)
                elif map_system:
                    wx, wy = token.world_x, token.world_y
                    sx, sy = map_system.world_to_screen(wx, wy)
                    sx, sy = int(sx), int(sy)
                else:
                    continue

                is_stereo = getattr(token, "is_stereo", False)
                z_mm = getattr(token, "marker_z", 0.0)

                if is_stereo:
                    label = f"#{token.id} [STEREO] Z: {z_mm:.1f}mm"
                    color = (255, 255, 0, 255)  # Cyan
                    bg_color = (40, 40, 0)
                else:
                    label = f"#{token.id} [MONO] Z: {z_mm:.1f}mm"
                    color = (0, 165, 255, 255)  # Amber / Orange
                    bg_color = (0, 30, 60)

                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)

                min_x = min(sx - ring_r - 2, sx - lw // 2 - 8)
                max_x = max(sx + ring_r + 2, sx + lw // 2 + 8)
                min_y = sy - ring_r - lh - 18
                max_y = sy + ring_r + 2

                patch_x1 = max(0, min_x)
                patch_y1 = max(0, min_y)
                patch_w = max(1, max_x - patch_x1)
                patch_h = max(1, max_y - patch_y1)

                token_buf = np.zeros((patch_h, patch_w, 4), dtype=np.uint8)
                lsx = sx - patch_x1
                lsy = sy - patch_y1

                # Indicator ring
                if is_stereo:
                    cv2.circle(token_buf, (lsx, lsy), ring_r, color, 2)
                    cv2.circle(token_buf, (lsx, lsy), ring_r - 4, color, 1)
                else:
                    draw_dashed_circle(token_buf, (lsx, lsy), ring_r, color, 2)

                # Text badge above token
                text_x = max(2, lsx - lw // 2)
                text_y = max(lh + 2, lsy - ring_r - 6)
                draw_text_with_background(
                    token_buf,
                    label,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    bg_color=bg_color,
                    alpha=0.85,
                )

                patches.append(
                    ImagePatch(
                        x=patch_x1,
                        y=patch_y1,
                        width=patch_w,
                        height=patch_h,
                        data=token_buf,
                    )
                )

        return patches

    def draw_notifications(self) -> list[ImagePatch]:
        patches = []
        notifications = self.context.notifications.get_active_notifications()
        if not notifications:
            # Return an empty patch at the notification location to clear it
            # This is critical for the layered renderer to know it should clear the cache.
            empty = np.zeros((1, 1, 4), dtype=np.uint8)
            patches.append(ImagePatch(x=50, y=100, width=1, height=1, data=empty))
            return patches

        # For simplicity, render all active notifications in one patch
        # starting at fixed position
        max_w = 0
        for msg in notifications:
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
            max_w = max(max_w, tw + 20)

        h_per_msg = 40
        total_h = len(notifications) * h_per_msg + 20
        buffer = np.zeros((total_h, max_w, 4), dtype=np.uint8)

        for i, msg in enumerate(notifications):
            draw_text_with_background(
                buffer,
                msg,
                (10, 30 + i * h_per_msg),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255, 255),
                2,
            )

        patches.append(ImagePatch(x=50, y=100, width=max_w, height=total_h, data=buffer))
        return patches
