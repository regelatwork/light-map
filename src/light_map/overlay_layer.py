from typing import List
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

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []

        patches = []

        # 1. Ghost Tokens
        if self.context.show_tokens:
            patches.extend(self.overlay_renderer.draw_ghost_tokens(self.time_provider))

        # 2. Notifications
        patches.extend(self.overlay_renderer.draw_notifications())

        # 3. Debug Overlay
        if self.context.debug_mode:
            patches.extend(
                self.overlay_renderer.draw_debug_overlay(
                    self.state.fps,
                    self.state.current_scene_name,
                    self.state.inputs,
                )
            )

        # Update tracking
        self._last_debug_mode = self.context.debug_mode
        self._last_show_tokens = self.context.show_tokens

        return patches

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = max(
                self.state.notifications_timestamp,
                self.state.tokens_timestamp,
                self.state.hands_timestamp,
            )
