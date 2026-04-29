from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from light_map.core.common_types import TimerKey


if TYPE_CHECKING:
    from light_map.state.temporal_event_manager import TemporalEventManager
    from light_map.state.versioned_atom import VersionedAtom


@dataclass
class Notification:
    """Represents a single notification message."""

    message: str
    timestamp: float = field(default_factory=time.monotonic)
    duration: float = 5.0  # seconds

    def refresh(self, time_provider: Callable[[], float] = time.monotonic):
        """Resets the timestamp to the current time."""
        self.timestamp = time_provider()


class NotificationManager:
    """Manages creation, display, and expiry of notifications using atomic state."""

    def __init__(
        self,
        time_provider: Callable[[], float] = time.monotonic,
        events: TemporalEventManager | None = None,
        atom: VersionedAtom | None = None,
    ):
        self.time_provider = time_provider
        self.events = events
        self.atom = atom

    @property
    def timestamp(self) -> int:
        """Returns the timestamp of the notifications atom."""
        return self.atom.timestamp if self.atom else 0

    def add_notification(self, message: str, duration: float = 5.0):
        """
        Adds a new notification or refreshes an existing one with the same message.
        """
        if not self.atom:
            return

        # Use current notifications list from atom
        notifications = self.atom.value[:]
        existing = None
        for n in notifications:
            if n.message == message:
                existing = n
                break

        if existing:
            existing.refresh(self.time_provider)
            existing.duration = duration
            # Re-update atom to trigger re-render if timestamp changed
            self.atom.update(notifications)
        else:
            notifications.append(
                Notification(message, timestamp=self.time_provider(), duration=duration)
            )
            self.atom.update(notifications)

        # Schedule expiry using declarative mutation
        if self.events:
            self.events.schedule_mutation(
                self.atom,
                lambda current, msg=message: [n for n in current if n.message != msg],
                duration,
                key=(TimerKey.NOTIFICATION_EXPIRY, message),
            )

    def _remove_notification(self, message: str):
        """Removes a specific notification by its message (Callback-based, deprecated)."""
        if not self.atom:
            return
        original = self.atom.value
        new_list = [n for n in original if n.message != message]
        if len(new_list) != len(original):
            self.atom.update(new_list)

    def _prune_expired(self):
        """Removes notifications that have exceeded their duration (No-op if events manager is present)."""
        if self.events or not self.atom:
            return

        current_time = self.time_provider()
        original = self.atom.value
        new_list = [n for n in original if current_time - n.timestamp < n.duration]
        if len(new_list) != len(original):
            self.atom.update(new_list)

    def get_active_notifications(self) -> list[str]:
        """Returns a list of messages for currently active notifications."""
        self._prune_expired()
        return [n.message for n in self.atom.value] if self.atom else []
