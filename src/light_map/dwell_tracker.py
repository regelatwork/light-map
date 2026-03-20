import math
from typing import Tuple, Optional, Callable
from light_map.core.temporal_event_manager import TemporalEventManager
from light_map.common_types import TimerKey, Action


class DwellTracker:
    """
    Tracks how long a pointer stays within a small radius.
    Useful for triggering interactions (select, toggle) without discrete clicks.
    """

    def __init__(
        self,
        radius_pixels: float,
        events: TemporalEventManager,
        dwell_time_threshold: float = 2.0,
        on_trigger: Optional[Callable[[], None]] = None,
    ):
        self.radius_pixels = radius_pixels
        self.dwell_time_threshold = dwell_time_threshold
        self.events = events
        self.on_trigger = on_trigger

        self.last_point: Optional[Tuple[float, float]] = None
        self.is_triggered = False
        self._just_triggered = False
        self._event_key = (TimerKey.DWELL, id(self))
        self.target_id: Optional[str] = None

    @property
    def accumulated_time(self) -> float:
        """Returns the time spent dwelling in seconds."""
        if self.is_triggered:
            return self.dwell_time_threshold
        if not self.events.has_event(self._event_key):
            return 0.0
        remaining = self.events.get_remaining_time(self._event_key)
        return max(0.0, self.dwell_time_threshold - remaining)

    @accumulated_time.setter
    def accumulated_time(self, value: float):
        # Kept for compatibility with InteractiveApp during transition,
        # but does nothing now as we use TemporalEventManager
        pass

    def update(
        self,
        point: Optional[Tuple[float, float]],
        dt: float,
        target_id: Optional[str] = None,
    ) -> bool:
        """
        Updates the tracker with a new point.
        Returns True if the dwell threshold has just been reached.
        """
        # We MUST check background trigger first
        if self._just_triggered:
            self._just_triggered = False
            return True

        if point is None:
            return False

        if self.last_point is None or target_id != self.target_id:
            self.last_point = point
            self.target_id = target_id
            self.is_triggered = False
            self._just_triggered = False
            self.events.schedule(
                self.dwell_time_threshold, self._trigger, key=self._event_key
            )
            return False

        # Calculate distance
        dist = math.sqrt(
            (point[0] - self.last_point[0]) ** 2 + (point[1] - self.last_point[1]) ** 2
        )

        if dist <= self.radius_pixels:
            if not self.is_triggered and not self.events.has_event(self._event_key):
                self.events.schedule(
                    self.dwell_time_threshold, self._trigger, key=self._event_key
                )
        else:
            # Reset if moved outside radius
            self.last_point = point
            self.is_triggered = False
            self._just_triggered = False
            self.events.cancel(self._event_key)
            self.events.schedule(
                self.dwell_time_threshold, self._trigger, key=self._event_key
            )

        return False

    def reset(self):
        """Resets the tracker state."""
        self.last_point = None
        self.is_triggered = False
        self._just_triggered = False
        self.events.cancel(self._event_key)

    def _trigger(self):
        if not self.is_triggered:
            self.is_triggered = True
            self._just_triggered = True
            if self.on_trigger:
                self.on_trigger()
            return Action.DWELL_TRIGGER
