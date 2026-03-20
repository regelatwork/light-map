from __future__ import annotations
import time
from typing import List, Set, Optional, TYPE_CHECKING
from light_map.common_types import GestureType, Action, TimerKey

if TYPE_CHECKING:
    from light_map.core.temporal_event_manager import TemporalEventManager


class InputManager:
    """
    Unifies hardware (keyboard) and vision (gesture) inputs into semantic Actions.
    """

    def __init__(
        self,
        flicker_timeout: float = 0.5,
        time_provider=time.monotonic,
        events: Optional[TemporalEventManager] = None,
    ):
        self.flicker_timeout = flicker_timeout
        self.time_provider = time_provider
        self.events = events
        self.is_present: bool = False

        self._x: int = 0
        self._y: int = 0
        self._gesture: GestureType = GestureType.NONE
        self._pending_actions: Set[Action] = set()

    def update(self, x: int, y: int, gesture: GestureType, is_present: bool):
        """Updates the internal state from vision detection."""
        was_present = self.is_hand_present()

        if is_present:
            self.is_present = True
            self._x = x
            self._y = y
            self._gesture = gesture
            # Cancel any pending timeout
            if self.events:
                self.events.cancel(TimerKey.GESTURE_TIMEOUT)
        else:
            # Check for flicker recovery
            if self.events:
                if not self.events.has_event(TimerKey.GESTURE_TIMEOUT):
                    self.events.schedule(
                        self.flicker_timeout,
                        self._clear_gesture,
                        key=TimerKey.GESTURE_TIMEOUT,
                    )
            else:
                # Fallback if no events manager provided (immediate clear)
                self._clear_gesture()

        # Map gesture to action ONLY IF newly present or gesture changed
        if self.is_hand_present() and (not was_present or gesture != self._gesture):
            # Update internal gesture before mapping if it changed during flicker recovery
            if not is_present and was_present:
                # We are in flicker recovery, maintain old gesture for action mapping
                # unless it already changed.
                pass
            else:
                self._gesture = gesture

            gesture_action = self._map_gesture_to_action(self._gesture)
            if gesture_action:
                self._pending_actions.add(gesture_action)

    def _clear_gesture(self):
        """Callback to clear gesture state when timeout expires."""
        if self.is_present:
            import logging

            logging.debug("InputManager: Gesture CLEARED due to timeout")
        self.is_present = False
        self._gesture = GestureType.NONE
        # Note: self.events.check() already removed this event from self._keys
        # so has_event(GESTURE_TIMEOUT) will return False now.

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
        elif char == ord("q") or char == ord("Q"):
            self._pending_actions.add(Action.QUIT)
        elif char == ord("d") or char == ord("D"):
            self._pending_actions.add(Action.TOGGLE_DEBUG)

    def _map_gesture_to_action(self, gesture: GestureType) -> Optional[Action]:
        if gesture in [GestureType.VICTORY, GestureType.OPEN_PALM]:
            return Action.SELECT
        elif gesture == GestureType.CLOSED_FIST:
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
        if self.is_present:
            return True
        if self.events and self.events.has_event(TimerKey.GESTURE_TIMEOUT):
            return True
        return False
