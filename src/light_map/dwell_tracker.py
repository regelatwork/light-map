import math
from typing import Tuple, Optional


class DwellTracker:
    """
    Tracks how long a pointer stays within a small radius.
    Useful for triggering interactions (select, toggle) without discrete clicks.
    """

    def __init__(self, radius_pixels: float, dwell_time_threshold: float = 2.0):
        self.radius_pixels = radius_pixels
        self.dwell_time_threshold = dwell_time_threshold

        self.last_point: Optional[Tuple[float, float]] = None
        self.accumulated_time = 0.0
        self.is_triggered = False

    def update(self, point: Optional[Tuple[float, float]], dt: float) -> bool:
        """
        Updates the tracker with a new point.
        Returns True if the dwell threshold has just been reached.
        """
        if point is None:
            self.reset()
            return False

        if self.last_point is None:
            self.last_point = point
            self.accumulated_time = 0.0
            self.is_triggered = False
            return False

        # Calculate distance
        dist = math.sqrt(
            (point[0] - self.last_point[0]) ** 2 + (point[1] - self.last_point[1]) ** 2
        )

        if dist <= self.radius_pixels:
            self.accumulated_time += dt
            if (
                self.accumulated_time >= self.dwell_time_threshold
                and not self.is_triggered
            ):
                self.is_triggered = True
                return True
        else:
            # Reset if moved outside radius
            self.last_point = point
            self.accumulated_time = 0.0
            self.is_triggered = False

        return False

    def reset(self):
        """Resets the tracker state."""
        self.last_point = None
        self.accumulated_time = 0.0
        self.is_triggered = False
