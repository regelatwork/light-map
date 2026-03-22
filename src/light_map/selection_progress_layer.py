import cv2
import numpy as np
from typing import List
from .common_types import Layer, ImagePatch
from .core.world_state import WorldState
from .core.app_context import AppContext
from .constants import (
    CURSOR_RADIUS,
    CURSOR_COLOR_BGRA,
)


class SelectionProgressLayer(Layer):
    """
    Renders selection progress indicators (rings/arcs) around the cursor.
    Separated from CursorLayer for better separation of concerns.
    """

    def __init__(self, state: WorldState, context: AppContext):
        super().__init__(state=state, is_static=False)
        self.context = context

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        # Sync with hands (movement), dwell state (progress), and summoning progress
        return max(
            self.state.hands_version,
            self.state.dwell_state_version,
            self.state.summon_progress_version,
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.state is None or not self.state.inputs:
            return []

        patches = []

        for hand in self.state.inputs:
            cp = hand.cursor_pos
            if cp is None:
                continue

            cx, cy = cp

            # --- RENDER PROGRESS RINGS ---
            radius = CURSOR_RADIUS
            ring_radius = radius + 4

            # Buffer size to contain the progress ring
            w, h = ring_radius * 2 + 6, ring_radius * 2 + 6
            buffer = np.zeros((h, w, 4), dtype=np.uint8)
            center = (w // 2, h // 2)
            color = CURSOR_COLOR_BGRA

            has_indicator = False

            # 1. Draw selection progress ring (Dwell)
            dwell_state = self.state.dwell_state
            if dwell_state and dwell_state.get("target_id"):
                acc = dwell_state.get("accumulated_time", 0.0)
                threshold = dwell_state.get("dwell_time_threshold", 2.0)
                if 0 < acc < threshold:
                    angle = int(360 * (acc / threshold))
                    # Background circle for progress
                    cv2.circle(buffer, center, ring_radius, (128, 128, 128, 128), 1)
                    # Progress arc
                    cv2.ellipse(
                        buffer,
                        center,
                        (ring_radius, ring_radius),
                        -90,  # Start from top
                        0,
                        angle,
                        color,
                        2,
                    )
                    has_indicator = True

            # 2. Draw menu summon progress ring
            if self.state.summon_progress > 0:
                angle = int(360 * self.state.summon_progress)
                # Use Cyan (255, 255, 0, 255) for summoning progress
                summon_color = (255, 255, 0, 255)
                # Background circle
                cv2.circle(buffer, center, ring_radius, (128, 128, 128, 128), 1)
                # Progress arc
                cv2.ellipse(
                    buffer,
                    center,
                    (ring_radius, ring_radius),
                    -90,
                    0,
                    angle,
                    summon_color,
                    2,
                )
                has_indicator = True

            if has_indicator:
                patches.append(
                    ImagePatch(
                        x=cx - w // 2, y=cy - h // 2, width=w, height=h, data=buffer
                    )
                )

        return patches
