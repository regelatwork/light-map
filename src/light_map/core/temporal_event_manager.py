import heapq
import time
from typing import Callable, Any, List, Tuple, Dict, Optional


class TemporalEventManager:
    """
    Time-Based Event Scheduler for the MainLoop.
    Allows the application to schedule state mutations in the future.
    Supports cancellation using unique event keys.
    """

    def __init__(self, time_provider: Callable[[], float] = time.monotonic):
        self.time_provider = time_provider
        # Priority queue: (target_time, callback, key)
        self._events: List[Tuple[float, Callable[[], Any], Optional[str]]] = []
        # Index for cancellation: key -> target_time (to detect stale heap entries)
        self._keys: Dict[str, float] = {}

    def schedule(
        self, delay: float, callback: Callable[[], Any], key: Optional[str] = None
    ):
        """
        Schedules a callback to be executed after `delay` seconds.
        If a key is provided and already exists, the old event is effectively replaced.
        """
        target_time = self.time_provider() + delay
        if key:
            self._keys[key] = target_time

        heapq.heappush(self._events, (target_time, callback, key))

    def has_event(self, key: str) -> bool:
        """Checks if an event with the given key is currently scheduled."""
        return key in self._keys

    def cancel(self, key: str):
        """
        Cancels a scheduled event by its key.
        """
        if key in self._keys:
            del self._keys[key]

    def check(self):
        """
        Checks for expired events and executes them.
        Should be called every tick of the main loop.
        """
        current_time = self.time_provider()

        while self._events and self._events[0][0] <= current_time:
            # Pop the earliest event
            target_time, callback, key = heapq.heappop(self._events)

            # If it has a key, check if it was cancelled or replaced
            if key is not None:
                if key not in self._keys or self._keys[key] != target_time:
                    # This event was cancelled or superseded by a later one with the same key
                    continue
                # Event is valid, clear the key entry
                del self._keys[key]

            try:
                callback()
            except Exception as e:
                # Log but don't stop the main loop
                import logging

                logging.error(f"Error executing temporal event: {e}")

    def clear(self):
        """Clears all pending events."""
        self._events.clear()
        self._keys.clear()
