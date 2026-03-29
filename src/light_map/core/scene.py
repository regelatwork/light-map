from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

import numpy as np

from light_map.common_types import GestureType, SceneId

if TYPE_CHECKING:
    from .app_context import AppContext
    from light_map.interactive_app import InteractiveApp
    from light_map.common_types import Layer, Action


@dataclass
class HandInput:
    """A standardized representation of a single hand's input state."""

    gesture: GestureType
    proj_pos: Tuple[int, int]  # (x, y) in projector space
    unit_direction: Tuple[
        float, float
    ]  # (dx, dy) normalized direction vector of finger
    raw_landmarks: Any  # MediaPipe landmarks for advanced processing if needed

    @property
    def cursor_pos(self) -> Optional[Tuple[int, int]]:
        """
        Returns the virtual pointer position (1-inch extension) if pointing.
        Requires ppi to be provided via context or external calculation.
        """
        from light_map.common_types import GestureType

        if self.gesture != GestureType.POINTING:
            return None

        # Extension distance logic could be moved here if we pass PPI,
        # but for now we'll keep the raw logic in the layer or a helper.
        # Actually, let's just make it a data field set by InputProcessor.
        return getattr(self, "_cursor_pos", None)

    @cursor_pos.setter
    def cursor_pos(self, value: Tuple[int, int]):
        self._cursor_pos = value


@dataclass
class SceneTransition:
    """An object returned by a Scene to request a change to a different Scene."""

    target_scene: SceneId
    payload: Any = None
    reset_history: bool = False


class Scene(ABC):
    """Abstract Base Class for all Scenes."""

    def __init__(self, context: AppContext):
        self.context = context

    @property
    def version(self) -> int:
        """
        Returns the current scene version from WorldState.
        Scenes do not store their own versions; they trigger updates in the central state.
        """
        return self.context.state.scene_version

    @property
    def blocking(self) -> bool:
        """True if the scene should block layers below it (opaque background)."""
        return False

    @property
    def show_tokens(self) -> bool:
        """True if tokens should be rendered by the overlay layer in this scene."""
        return True

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Returns the list of layers that should be active for this scene."""
        return app.layer_stack

    def get_standard_ui_stack(self, app: InteractiveApp) -> List[Layer]:
        """
        Returns the standard set of overlay layers (Bottom to Top).
        Useful for scenes that want a clean UI-only view (e.g., Menu, Setup).
        """
        return [
            app.aruco_mask_layer,
            app.hand_mask_layer,
            app.token_layer,  # Hidden if show_tokens is False, but should be below menu regardless
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.selection_progress_layer,
            app.cursor_layer,
        ]

    def get_scene_with_ui_stack(self, app: InteractiveApp) -> List[Layer]:
        """
        Returns the scene layer plus standard UI overlay layers.
        Useful for scenes that show interactive content (e.g., Calibration, Scanning).
        """
        return [app.scene_layer] + self.get_standard_ui_stack(app)

    def on_enter(self, payload: Any = None) -> None:
        """Called once when the scene becomes active."""
        pass

    def on_exit(self) -> None:
        """Called once when the scene is deactivated."""
        pass

    @abstractmethod
    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        """Processes input and returns a transition request if any."""
        raise NotImplementedError

    @abstractmethod
    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the scene's visual output. Returns the modified frame."""
        raise NotImplementedError
