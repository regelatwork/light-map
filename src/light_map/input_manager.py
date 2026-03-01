import time
from typing import List, Set, Optional
from light_map.common_types import GestureType, Action


class InputManager:
    """
    Unifies hardware (keyboard) and vision (gesture) inputs into semantic Actions.
    """

    def __init__(self, flicker_timeout: float = 0.5, time_provider=time.monotonic):
        self.flicker_timeout = flicker_timeout
        self.time_provider = time_provider
        self.last_present_time: float = 0.0
        self.is_present: bool = False

        self._x: int = 0
        self._y: int = 0
        self._gesture: GestureType = GestureType.NONE
        self._pending_actions: Set[Action] = set()

    def update(self, x: int, y: int, gesture: GestureType, is_present: bool):
        """Updates the internal state from vision detection."""
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
                self.is_present = True
            else:
                self.is_present = False
                self._gesture = GestureType.NONE

        # Map gesture to action
        if self.is_present:
            gesture_action = self._map_gesture_to_action(self._gesture)
            if gesture_action:
                self._pending_actions.add(gesture_action)

    def update_keyboard(self, key_code: int):
        """Processes a raw keyboard code from cv2.waitKey()."""
        if key_code == -1:
            return

        char = key_code & 0xFF

        # Simple mapping
        if char == ord("\r") or char == ord("\n") or char == ord(" "):
            self._pending_actions.add(Action.SELECT)
        elif char == 27 or char == ord("b"):  # ESC or 'b'
            self._pending_actions.add(Action.BACK)

    def _map_gesture_to_action(self, gesture: GestureType) -> Optional[Action]:
        if gesture in [GestureType.VICTORY, GestureType.CLOSED_FIST]:
            return Action.SELECT
        elif gesture == GestureType.OPEN_PALM:
            return Action.BACK
        elif gesture == GestureType.POINTING:
            return Action.MOVE
        return None

    def get_actions(self) -> List[Action]:
        """Returns the current pending actions and clears the set."""
        actions = list(self._pending_actions)
        self._pending_actions.clear()
        return actions

    def get_x(self) -> int:
        return self._x

    def get_y(self) -> int:
        return self._y

    def get_gesture(self) -> GestureType:
        return self._gesture

    def is_hand_present(self) -> bool:
        return self.is_present
