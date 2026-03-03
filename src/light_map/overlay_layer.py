from typing import List
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

    def __init__(
        self, state: WorldState, context: AppContext, time_provider=time.monotonic
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.time_provider = time_provider
        self.overlay_renderer = OverlayRenderer(context)

        # Cache tracking
        self._last_debug_mode = False
        self._last_show_tokens = True
        self._last_pulse_render_time = 0.0

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True

        now = self.time_provider()

        # Ghost tokens pulse (time-dependent), so they might need frequent re-render.
        # We throttle this to ~2 FPS (500ms) to avoid hogging CPU if nothing else changes.
        pulse_dirty = False
        if self.context.show_tokens and self.state.tokens:
            if now - self._last_pulse_render_time > 0.5:
                pulse_dirty = True

        if (
            pulse_dirty
            or self.state.notifications_timestamp > self._last_state_timestamp
            or self.state.tokens_timestamp > self._last_state_timestamp
            or self.state.hands_timestamp > self._last_state_timestamp
            or self.context.debug_mode != self._last_debug_mode
            or self.context.show_tokens != self._last_show_tokens
        ):
            if pulse_dirty:
                self._last_pulse_render_time = now
            return True

        return False

    def _generate_patches(self) -> List[ImagePatch]:
        if self.state is None:
            return []

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
                buffer_bgr,
                self.state.fps,
                self.state.current_scene_name,
                self.state.inputs,
            )

        # Convert to BGRA with alpha heuristic
        patch_data = np.zeros((height, width, 4), dtype=np.uint8)
        patch_data[:, :, :3] = buffer_bgr

        # Use fast bitwise OR for masking
        combined = buffer_bgr[:, :, 0] | buffer_bgr[:, :, 1] | buffer_bgr[:, :, 2]
        patch_data[combined > 0, 3] = 255

        patch = ImagePatch(x=0, y=0, width=width, height=height, data=patch_data)

        # Update tracking
        self._last_debug_mode = self.context.debug_mode
        self._last_show_tokens = self.context.show_tokens

        return [patch]

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = max(
                self.state.notifications_timestamp,
                self.state.tokens_timestamp,
                self.state.hands_timestamp,
            )
