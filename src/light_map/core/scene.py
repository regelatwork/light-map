from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

import numpy as np

from light_map.common_types import GestureType, SceneId

if TYPE_CHECKING:
    from .app_context import AppContext


@dataclass
class HandInput:
    """A standardized representation of a single hand's input state."""

    gesture: GestureType
    proj_pos: Tuple[int, int]  # (x, y) in projector space
    raw_landmarks: Any  # MediaPipe landmarks for advanced processing if needed


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
        self._is_dirty = True

    @property
    def is_dirty(self) -> bool:
        """True if the scene has visual changes since last render."""
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool):
        self._is_dirty = value

    def on_enter(self, payload: Any = None) -> None:
        """Called once when the scene becomes active."""
        pass

    def on_exit(self) -> None:
        """Called once when the scene is deactivated."""
        pass

    @abstractmethod
    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """Processes input and returns a transition request if any."""
        raise NotImplementedError

    @abstractmethod
    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the scene's visual output. Returns the modified frame."""
        raise NotImplementedError
