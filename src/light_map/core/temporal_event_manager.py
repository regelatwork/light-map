import heapq
import time
from typing import Callable, Any, List, Tuple


class TemporalEventManager:
    """
    Time-Based Event Scheduler for the MainLoop.
    Allows the application to schedule state mutations in the future.
    """

    def __init__(self, time_provider: Callable[[], float] = time.time):
        self.time_provider = time_provider
        # Priority queue: (target_time, callback)
        self._events: List[Tuple[float, Callable[[], Any]]] = []

    def schedule(self, delay: float, callback: Callable[[], Any]):
        """
        Schedules a callback to be executed after `delay` seconds.
        """
        target_time = self.time_provider() + delay
        heapq.heappush(self._events, (target_time, callback))

    def check(self):
        """
        Checks for expired events and executes them.
        Should be called every tick of the main loop.
        """
        current_time = self.time_provider()

        while self._events and self._events[0][0] <= current_time:
            # Pop the earliest event
            _, callback = heapq.heappop(self._events)
            try:
                callback()
            except Exception as e:
                # Log but don't stop the main loop
                import logging

                logging.error(f"Error executing temporal event: {e}")

    def clear(self):
        """Clears all pending events."""
        self._events.clear()
