from typing import List, Optional
import numpy as np
import time
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState
from .core.app_context import AppContext
from .vision.overlay_renderer import OverlayRenderer


class OverlayLayer(Layer):
    """
    Renders global UI elements (notifications, tokens, debug info).
    Uses OverlayRenderer and timestamps for caching.
    """

    def __init__(self, context: AppContext, time_provider=time.monotonic):
        super().__init__(layer_mode=LayerMode.NORMAL)
        self.context = context
        self.time_provider = time_provider
        self.overlay_renderer = OverlayRenderer(context)
        self._cached_patch: Optional[ImagePatch] = None

        # We also track internal state to force re-render if needed
        self._last_debug_mode = False
        self._last_show_tokens = True

    def render(self, state: WorldState) -> List[ImagePatch]:
        # Overlay layer is usually dynamic, but we can still cache if NOTHING changed.
        # However, ghost tokens pulse (time-dependent), so they might need frequent re-render.
        # For now, let's re-render if any relevant timestamp changed or time has passed (for pulse).

        # Cache check
        needs_rerender = (
            state.notifications_timestamp > self.last_rendered_timestamp
            or state.tokens_timestamp > self.last_rendered_timestamp
            or state.hands_timestamp > self.last_rendered_timestamp
            or self.context.debug_mode != self._last_debug_mode
            or self.context.show_tokens != self._last_show_tokens
            or self._cached_patch is None
        )

        # Force re-render for pulsing tokens if visible
        if self.context.show_tokens and state.tokens:
            needs_rerender = True

        if needs_rerender:
            width = self.context.app_config.width
            height = self.context.app_config.height

            # Create BGR buffer
            buffer_bgr = np.zeros((height, width, 3), dtype=np.uint8)

            # 1. Ghost Tokens
            if self.context.show_tokens:
                self.overlay_renderer.draw_ghost_tokens(buffer_bgr, self.time_provider)

            # 2. Notifications
            self.overlay_renderer.draw_notifications(buffer_bgr)

            # 3. Debug Overlay
            if self.context.debug_mode:
                self.overlay_renderer.draw_debug_overlay(
                    buffer_bgr, state.fps, state.current_scene_name, state.inputs
                )

            # Convert to BGRA with alpha heuristic
            patch_data = np.zeros((height, width, 4), dtype=np.uint8)
            patch_data[:, :, :3] = buffer_bgr

            mask = np.any(buffer_bgr > 0, axis=2)
            patch_data[mask, 3] = 255

            self._cached_patch = ImagePatch(
                x=0, y=0, width=width, height=height, data=patch_data
            )
            self.last_rendered_timestamp = max(
                state.notifications_timestamp,
                state.tokens_timestamp,
                state.hands_timestamp,
            )
            self._last_debug_mode = self.context.debug_mode
            self._last_show_tokens = self.context.show_tokens

        return [self._cached_patch] if self._cached_patch else []
