import cv2
import numpy as np
from typing import List, Tuple
from .common_types import Layer, ImagePatch
from .core.world_state import WorldState
from .core.app_context import AppContext


class CursorLayer(Layer):
    """
    Renders the interactive virtual pointer/cursor.
    Uses pre-calculated cursor positions from HandInput.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False)
        self.context = context
        self._last_cursor_positions: List[Tuple[int, int]] = []

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True

        # Cursor is dynamic, always re-render if hands are present or if they were present
        if self.state.hands_timestamp > self._last_state_timestamp:
            return True

        return False

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or not self.state.inputs:
            self._last_cursor_positions = []
            return []

        patches = []
        current_positions = []

        for hand in self.state.inputs:
            cp = hand.cursor_pos
            if cp is None:
                continue

            cx, cy = cp
            current_positions.append((cx, cy))

            # Render a small reticle or dot
            radius = 12
            # Buffer size to contain the cursor
            w, h = radius * 2 + 4, radius * 2 + 4
            buffer = np.zeros((h, w, 4), dtype=np.uint8)

            # Draw cursor (Yellow crosshair/circle)
            center = (w // 2, h // 2)
            color = (0, 255, 255, 255)  # BGRA Yellow
            cv2.circle(buffer, center, radius, color, 2)
            cv2.circle(buffer, center, 2, color, -1)

            # Crosshair lines
            cv2.line(
                buffer, (center[0] - 5, center[1]), (center[0] + 5, center[1]), color, 1
            )
            cv2.line(
                buffer, (center[0], center[1] - 5), (center[0], center[1] + 5), color, 1
            )

            patches.append(
                ImagePatch(x=cx - w // 2, y=cy - h // 2, width=w, height=h, data=buffer)
            )

        self._last_cursor_positions = current_positions
        return patches

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.hands_timestamp
