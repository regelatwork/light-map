from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple, Protocol

import numpy as np

from light_map.gestures import GestureType

if TYPE_CHECKING:
    from .scene import HandInput


class Transformable(Protocol):
    def pan(self, dx: float, dy: float) -> None: ...
    def zoom_pinned(self, factor: float, center_point: Tuple[int, int]) -> None: ...


class MapInteractionController:
    """A helper class to centralize pan/zoom math for map manipulation."""

    def __init__(self):
        self.panning_hand: Optional[Tuple[int, int]] = None
        self.zooming_hands: Optional[Tuple[float, Tuple[int, int]]] = None

    def process_gestures(self, inputs: List[HandInput], target: Transformable) -> bool:
        """
        Processes hand inputs to perform map interactions like pan and zoom.

        Args:
            inputs: A list of HandInput objects representing the current hands.
            target: The object to apply transformations to (e.g., MapSystem or GridOverlay).

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
                target.pan(delta_x, delta_y)
                interaction_occurred = True
            self.panning_hand = current_pos

        else:
            self.panning_hand = None
            self.zooming_hands = None

        return interaction_occurred
