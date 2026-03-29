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

        # Use time-based version for 500ms pulse if not dynamic
        pulse_version = int(now * 2)  # Increments every 0.5s

        if show_tokens and self.state.tokens and any_occluded:
            # Need every-frame updates for smooth occluded token persistence
            pulse_version = self.state.system_time_version

        v = max(
            self.state.tokens_version,
            self.state.grid_metadata_version,
            self.state.viewport_version,
        )
        # Combined version: include show_tokens in version to catch toggles.
        v = (v << 1) | (1 if show_tokens else 0)

        # Combine with pulse_version in a monotonic way.
        # Use a large enough multiplier for v to ensure pulse_version doesn't overflow into its bits.
        # Nanosecond timestamps are ~10^15, so 10^18 is safe.
        return v * 10**18 + pulse_version

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
        return self.state.notifications_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []
        return self.overlay_renderer.draw_notifications()


class DebugLayer(Layer):
    """
    Renders diagnostic information like FPS, resolution, and hand skeletons.
    Only visible when app.debug_mode is True.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.overlay_renderer = OverlayRenderer(context)
        self._last_debug_mode = False

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Catch debug toggle in version
        version = (self.state.hands_version << 1) | (
            1 if self.context.debug_mode else 0
        )
        # Also depend on FPS updates
        version = max(version, self.state.fps_version)
        return version

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
