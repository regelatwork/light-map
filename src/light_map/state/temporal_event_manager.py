import heapq
import logging
import time
from collections.abc import Callable, Hashable
from typing import Any

from light_map.state.versioned_atom import VersionedAtom
from light_map.state.world_state import WorldState


class TemporalEventManager:
    """
    Time-Based Event Scheduler for the MainLoop.
    Allows the application to schedule state mutations in the future.
    Supports cancellation using unique event keys.
    """

    def __init__(
        self,
        time_provider: Callable[[], float] = time.monotonic,
        state: WorldState | None = None,
    ):
        self.time_provider = time_provider
        self.state = state
        # Priority queue: (target_time, callback, key)
        self._events: list[tuple[float, Callable[[], Any], Hashable | None]] = []
        # Index for cancellation: key -> target_time (to detect stale heap entries)
        self._keys: dict[Hashable, float] = {}

    def advance(self, dt: float):
        """
        Increments the system time by dt.
        """
        if self.state:
            new_time = self.state.system_time + dt
            self.state._system_time_atom.update(new_time)

    def schedule(
        self, delay: float, callback: Callable[[], Any], key: Hashable | None = None
    ):
        """
        Schedules a callback to be executed after `delay` seconds.
        If a key is provided and already exists, the old event is effectively replaced.
        """
        target_time = self.time_provider() + delay
        if key is not None:
            self._keys[key] = target_time

        logging.debug(
            f"TemporalEventManager: Scheduled event (key={key}, delay={delay:.3f}s, target={target_time:.3f})"
        )
        heapq.heappush(self._events, (target_time, callback, key))

    def schedule_mutation(
        self,
        atom: VersionedAtom,
        new_value: Any,
        delay: float,
        key: Hashable | None = None,
    ):
        """
        Schedules an update to a VersionedAtom in the future.
        If new_value is a callable, it is called with the current value of the atom
        at the time of execution to determine the new value.
        """

        def perform_mutation():
            val = new_value(atom.value) if callable(new_value) else new_value
            atom.update(val)

        self.schedule(delay, perform_mutation, key=key)

    def has_event(self, key: Hashable) -> bool:
        """Checks if an event with the given key is currently scheduled."""
        return key in self._keys

    def cancel(self, key: Hashable):
        """
        Cancels a scheduled event by its key.
        """
        if key in self._keys:
            logging.debug(f"TemporalEventManager: Cancelling event (key={key})")
            del self._keys[key]

    def get_remaining_time(self, key: Hashable) -> float:
        """Returns the time remaining for an event with the given key."""
        if key not in self._keys:
            return 0.0
        return max(0.0, self._keys[key] - self.time_provider())

    def check(self) -> list[Any]:
        """
        Checks for expired events and executes them.
        Returns a list of values returned by the callbacks.
        Should be called every tick of the main loop.
        """
        current_time = self.time_provider()
        results = []

        while self._events and self._events[0][0] <= current_time:
            # Pop the earliest event
            target_time, callback, key = heapq.heappop(self._events)

            # If it has a key, check if it was cancelled or replaced
            if key is not None:
                if key not in self._keys or self._keys[key] != target_time:
                    # This event was cancelled or superseded by a later one with the same key
                    logging.debug(
                        f"TemporalEventManager: Skipping stale/cancelled event (key={key}, target={target_time:.3f})"
                    )
                    continue
                # Event is valid, clear the key entry
                del self._keys[key]

            logging.debug(
                f"TemporalEventManager: Triggering event (key={key}, target={target_time:.3f})"
            )
            try:
                res = callback()
                if res is not None:
                    results.append(res)
            except Exception as e:
                # Log but don't stop the main loop
                logging.error(f"Error executing temporal event: {e}")

        return results

    def clear(self):
        """Clears all pending events."""
        if self._events or self._keys:
            logging.debug(
                f"TemporalEventManager: Clearing all events (count={len(self._events)})"
            )
        self._events.clear()
        self._keys.clear()
