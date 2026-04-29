from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import numpy as np

from light_map.input.gestures import GestureType


if TYPE_CHECKING:
    from light_map.input.scene import HandInput


class Transformable(Protocol):
    def pan(self, dx: float, dy: float) -> None: ...
    def zoom_pinned(self, factor: float, center_point: tuple[int, int]) -> None: ...


class MapInteractionController:
    """A helper class to centralize pan/zoom math for map manipulation."""

    def __init__(self):
        self.panning_hand: tuple[int, int] | None = None
        self.zooming_hands: tuple[float, tuple[int, int]] | None = None
        self.pan_accumulator: tuple[float, float] = (0.0, 0.0)

    def process_gestures(
        self,
        inputs: list[HandInput],
        target: Transformable,
        grid_size: float | None = None,
    ) -> bool:
        """
        Processes hand inputs to perform map interactions like pan and zoom.

        Args:
            inputs: A list of HandInput objects representing the current hands.
            target: The object to apply transformations to (e.g., MapSystem or GridOverlay).
            grid_size: Optional grid size to snap panning to.

        Returns:
            True if an interaction (pan or zoom) occurred, False otherwise.
        """
        interaction_occurred = False

        # Two-handed zoom
        if (
            len(inputs) == 2
            and inputs[0].gesture == GestureType.POINTING
            and inputs[1].gesture == GestureType.POINTING
        ):
            self.panning_hand = None
            self.pan_accumulator = (0.0, 0.0)
            pos1 = inputs[0].proj_pos
            pos2 = inputs[1].proj_pos
            distance = np.linalg.norm(np.array(pos1) - np.array(pos2))
            center_point = tuple(np.mean([pos1, pos2], axis=0).astype(int))

            if self.zooming_hands:
                prev_dist, _ = self.zooming_hands
                scale_factor = distance / prev_dist if prev_dist > 0 else 1.0
                target.zoom_pinned(scale_factor, center_point)
                interaction_occurred = True

            self.zooming_hands = (distance, center_point)

        # One-handed pan
        elif len(inputs) == 1 and inputs[0].gesture == GestureType.CLOSED_FIST:
            self.zooming_hands = None
            current_pos = inputs[0].proj_pos
            if self.panning_hand:
                prev_pos = self.panning_hand
                delta_x = current_pos[0] - prev_pos[0]
                delta_y = current_pos[1] - prev_pos[1]

                if grid_size and grid_size > 0:
                    self.pan_accumulator = (
                        self.pan_accumulator[0] + delta_x,
                        self.pan_accumulator[1] + delta_y,
                    )

                    pan_dx = 0.0
                    pan_dy = 0.0

                    if abs(self.pan_accumulator[0]) >= grid_size:
                        steps = int(self.pan_accumulator[0] / grid_size)
                        pan_dx = steps * grid_size
                        self.pan_accumulator = (
                            self.pan_accumulator[0] - pan_dx,
                            self.pan_accumulator[1],
                        )

                    if abs(self.pan_accumulator[1]) >= grid_size:
                        steps = int(self.pan_accumulator[1] / grid_size)
                        pan_dy = steps * grid_size
                        self.pan_accumulator = (
                            self.pan_accumulator[0],
                            self.pan_accumulator[1] - pan_dy,
                        )

                    if pan_dx != 0.0 or pan_dy != 0.0:
                        target.pan(pan_dx, pan_dy)
                        interaction_occurred = True
                else:
                    target.pan(delta_x, delta_y)
                    interaction_occurred = True
            self.panning_hand = current_pos

        else:
            self.panning_hand = None
            self.zooming_hands = None
            self.pan_accumulator = (0.0, 0.0)

        return interaction_occurred
