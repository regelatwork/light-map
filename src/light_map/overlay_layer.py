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

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True

        now = self.time_provider()
        show_tokens = getattr(
            self.state, "effective_show_tokens", self.context.show_tokens
        )

        # Pulse every 500ms
        pulse_dirty = False
        if show_tokens and self.state.tokens:
            if now - self._last_pulse_render_time > 0.5:
                pulse_dirty = True

        if (
            pulse_dirty
            or self.state.tokens_timestamp > self._last_state_timestamp
            or show_tokens != self._last_show_tokens
        ):
            if pulse_dirty:
                self._last_pulse_render_time = now
            return True

        return False

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

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.tokens_timestamp


class NotificationLayer(Layer):
    """
    Renders system notifications.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.overlay_renderer = OverlayRenderer(context)

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True
        return self.state.notifications_timestamp > self._last_state_timestamp

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None:
            return []
        return self.overlay_renderer.draw_notifications()

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.notifications_timestamp


class DebugLayer(Layer):
    """
    Renders debug information (FPS, scene name, hand inputs).
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.context = context
        self.overlay_renderer = OverlayRenderer(context)
        self._last_debug_mode = False

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True

        if (
            self.state.hands_timestamp > self._last_state_timestamp
            or self.context.debug_mode != self._last_debug_mode
            or True  # Always dirty if debug mode is on to update FPS
        ):
            return (
                self.context.debug_mode
                or self.context.debug_mode != self._last_debug_mode
            )

        return False

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

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.hands_timestamp
