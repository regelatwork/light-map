
import cv2
import numpy as np

from light_map.core.app_context import AppContext
from light_map.core.common_types import ImagePatch, Layer
from light_map.core.constants import (
    CURSOR_COLOR_BGRA,
    CURSOR_CROSSHAIR_SIZE,
    CURSOR_RADIUS,
    CURSOR_THICKNESS,
)
from light_map.state.world_state import WorldState


class CursorLayer(Layer):
    """
    Renders the interactive virtual pointer/cursor.
    Uses pre-calculated cursor positions from HandInput.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False)
        self.context = context
        self._last_cursor_positions: list[tuple[int, int]] = []

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(self.state.hands_version, self.state.projector_pose_version)

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
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
            radius = CURSOR_RADIUS
            # Buffer size to contain the cursor
            w, h = radius * 2 + 4, radius * 2 + 4
            buffer = np.zeros((h, w, 4), dtype=np.uint8)

            # Draw cursor (Yellow crosshair/circle)
            center = (w // 2, h // 2)
            color = CURSOR_COLOR_BGRA
            cv2.circle(buffer, center, radius, color, CURSOR_THICKNESS)
            cv2.circle(buffer, center, 2, color, -1)

            # Crosshair lines
            cv2.line(
                buffer,
                (center[0] - CURSOR_CROSSHAIR_SIZE, center[1]),
                (center[0] + CURSOR_CROSSHAIR_SIZE, center[1]),
                color,
                1,
            )
            cv2.line(
                buffer,
                (center[0], center[1] - CURSOR_CROSSHAIR_SIZE),
                (center[0], center[1] + CURSOR_CROSSHAIR_SIZE),
                color,
                1,
            )

            patches.append(
                ImagePatch(x=cx - w // 2, y=cy - h // 2, width=w, height=h, data=buffer)
            )

        self._last_cursor_positions = current_positions
        return patches
