import time
from src.light_map.common_types import GestureType


class InputManager:
    def __init__(self, flicker_timeout: float = 0.5, time_provider=time.monotonic):
        self.flicker_timeout = flicker_timeout
        self.time_provider = time_provider
        self.last_present_time: float = 0.0
        self.is_present: bool = False

        self._x: int = 0
        self._y: int = 0
        self._gesture: GestureType = GestureType.NONE

    def update(self, x: int, y: int, gesture: GestureType, is_present: bool):
        now = self.time_provider()

        if is_present:
            self.last_present_time = now
            self.is_present = True
            self._x = x
            self._y = y
            self._gesture = gesture
        else:
            # Check for flicker recovery
            if now - self.last_present_time < self.flicker_timeout:
                # Still within recovery window, pretend hand is there
                # We keep the old _x, _y, _gesture
                self.is_present = True
            else:
                self.is_present = False
                # Optional: Reset or keep stale values.
                # Keeping stale values is safer if accidentally accessed,
                # but is_present should guard it.
                self._gesture = GestureType.NONE

    def get_x(self) -> int:
        return self._x

    def get_y(self) -> int:
        return self._y

    def get_gesture(self) -> GestureType:
        return self._gesture

    def is_hand_present(self) -> bool:
        return self.is_present
