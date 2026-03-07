import time
from dataclasses import dataclass, field
from typing import List, Callable


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
    """Manages creation, display, and expiry of notifications."""

    def __init__(self, time_provider: Callable[[], float] = time.monotonic):
        self.notifications: List[Notification] = []
        self.timestamp: int = 0
        self.time_provider = time_provider

    def add_notification(self, message: str, duration: float = 5.0):
        """
        Adds a new notification or refreshes an existing one with the same message.
        """
        # Search for existing message to refresh its duration
        for n in self.notifications:
            if n.message == message:
                n.refresh(self.time_provider)
                n.duration = duration
                # We don't necessarily need to bump the global timestamp if content is identical,
                # but it ensures the layer keeps rendering if it needs to.
                return

        self.notifications.append(
            Notification(message, timestamp=self.time_provider(), duration=duration)
        )
        self.timestamp += 1

    def _prune_expired(self):
        """Removes notifications that have exceeded their duration."""
        current_time = self.time_provider()
        original_count = len(self.notifications)
        self.notifications = [
            n for n in self.notifications if current_time - n.timestamp < n.duration
        ]
        if len(self.notifications) != original_count:
            self.timestamp += 1

    def get_active_notifications(self) -> List[str]:
        """Returns a list of messages for currently active notifications."""
        self._prune_expired()
        return [n.message for n in self.notifications]
