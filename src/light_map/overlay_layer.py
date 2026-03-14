from typing import List
import time
from .common_types import Layer, LayerMode, ImagePatch
from .core.world_state import WorldState
from .core.app_context import AppContext
from .vision.overlay_renderer import OverlayRenderer


class TokenLayer(Layer):
    """
    Renders ghost tokens on the map.
    """

    def __init__(
        self, state: WorldState, context: AppContext, time_provider=time.monotonic
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.time_provider = time_provider
        self.overlay_renderer = OverlayRenderer(context)
        self._last_show_tokens = True
        self._last_pulse_render_time = 0.0

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        now = self.time_provider()
        show_tokens = getattr(
            self.state, "effective_show_tokens", self.context.show_tokens
        )

        # Pulse logic: If any token is occluded, we need to pulse every frame for smoothness.
        # Otherwise, we pulse every 500ms for static ghost tokens to show they are "live".
        any_occluded = any(t.is_occluded for t in self.state.tokens)

        self._is_dynamic = False
        if show_tokens and self.state.tokens:
            if any_occluded:
                self._is_dynamic = True
            elif now - self._last_pulse_render_time > 0.5:
                # We trigger ONE render pass by incrementing version or just returning dirty?
                # Actually, _is_dynamic = True for one frame is hard.
                # Let's just return a higher version if 500ms passed.
                pass

        # Use time-based version for 500ms pulse if not dynamic
        time_version = int(now * 2)  # Increments every 0.5s

        # Combined version: include show_tokens in version to catch toggles.
        # We use a bit-shift or large offset to ensure it's different.
        v = (self.state.tokens_timestamp << 1) | (1 if show_tokens else 0)
        return max(v, time_version if show_tokens else 0)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []

        show_tokens = getattr(
            self.state, "effective_show_tokens", self.context.show_tokens
        )
        self._last_show_tokens = show_tokens

        if not show_tokens:
            return []

        return self.overlay_renderer.draw_ghost_tokens(self.time_provider)


class NotificationLayer(Layer):
    """
    Renders system notifications.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.overlay_renderer = OverlayRenderer(context)

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return self.state.notifications_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []
        return self.overlay_renderer.draw_notifications()


class DebugLayer(Layer):
    """
    Renders debug information (FPS, scene name, hand inputs).
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.overlay_renderer = OverlayRenderer(context)
        self._last_debug_mode = False

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        self._is_dynamic = self.context.debug_mode
        # Catch debug toggle in version
        return (self.state.hands_timestamp << 1) | (1 if self.context.debug_mode else 0)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or not self.context.debug_mode:
            self._last_debug_mode = self.context.debug_mode
            return []

        self._last_debug_mode = self.context.debug_mode
        return self.overlay_renderer.draw_debug_overlay(
            self.state.fps,
            self.state.current_scene_name,
            self.state.inputs,
        )
