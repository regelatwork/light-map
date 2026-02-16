import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class Notification:
    """Represents a single notification message."""

    message: str
    timestamp: float = field(default_factory=time.time)
    duration: float = 5.0  # seconds


class NotificationManager:
    """Manages creation, display, and expiry of notifications."""

    def __init__(self):
        self.notifications: List[Notification] = []

    def add_notification(self, message: str, duration: float = 5.0):
        """Adds a new notification to the manager."""
        self.notifications.append(Notification(message, duration=duration))

    def _prune_expired(self):
        """Removes notifications that have exceeded their duration."""
        current_time = time.time()
        self.notifications = [
            n for n in self.notifications if current_time - n.timestamp < n.duration
        ]

    def get_active_notifications(self) -> List[str]:
        """Returns a list of messages for currently active notifications."""
        self._prune_expired()
        return [n.message for n in self.notifications]
