import math
from typing import Tuple, Optional, Callable
from light_map.core.temporal_event_manager import TemporalEventManager


class DwellTracker:
    """
    Tracks how long a pointer stays within a small radius.
    Useful for triggering interactions (select, toggle) without discrete clicks.
    """

    def __init__(
        self,
        radius_pixels: float,
        dwell_time_threshold: float = 2.0,
        events: Optional[TemporalEventManager] = None,
        on_trigger: Optional[Callable[[], None]] = None,
    ):
        self.radius_pixels = radius_pixels
        self.dwell_time_threshold = dwell_time_threshold
        self.events = events
        self.on_trigger = on_trigger

        self.last_point: Optional[Tuple[float, float]] = None
        self.accumulated_time = 0.0
        self.is_triggered = False
        self._just_triggered = False
        self._event_key = f"dwell_{id(self)}"

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
            self._just_triggered = False
            if self.events:
                self.events.schedule(self.dwell_time_threshold, self._trigger, key=self._event_key)
            return False

        # Calculate distance
        dist = math.sqrt(
            (point[0] - self.last_point[0]) ** 2 + (point[1] - self.last_point[1]) ** 2
        )

        if dist <= self.radius_pixels:
            if not self.events:
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
            self._just_triggered = False
            if self.events:
                self.events.schedule(self.dwell_time_threshold, self._trigger, key=self._event_key)

        # Async trigger check for TemporalEventManager
        if self._just_triggered:
            self._just_triggered = False
            return True

        return False

    def reset(self):
        """Resets the tracker state."""
        self.last_point = None
        self.accumulated_time = 0.0
        self.is_triggered = False
        self._just_triggered = False
        if self.events:
            self.events.cancel(self._event_key)

    def _trigger(self):
        if not self.is_triggered:
            self.is_triggered = True
            self._just_triggered = True
            if self.on_trigger:
                self.on_trigger()
