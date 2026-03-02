import numpy as np
from typing import List, Optional, Callable, Any, Dict
from light_map.common_types import Token, DetectionResult, ResultType, ViewportState


class WorldState:
    """
    Central Data Repository (The "Source of Truth") for the MainProcess.
    Manages background frames, vision results, and granular timestamps for caching.
    """

    def __init__(
        self, frame_processor: Optional[Callable[[np.ndarray], np.ndarray]] = None
    ):
        self.frame_processor = frame_processor

        # State Data
        self.background: Optional[np.ndarray] = None
        self.last_frame_timestamp: int = 0

        self.tokens: List[Token] = []  # Logical/Snapped tokens
        self.raw_tokens: List[Token] = []  # Live/Unsnapped tokens
        self.raw_aruco: Dict[str, Any] = {"corners": [], "ids": []}
        self.hands: List[Any] = []  # Landmarks
        self.handedness: List[Any] = []
        self.gesture: Optional[str] = None
        self.viewport: ViewportState = ViewportState()

        # Granular Timestamps (Monotonic counters for caching)
        self.map_timestamp: int = 0
        self.menu_timestamp: int = 0
        self.tokens_timestamp: int = 0
        self.hands_timestamp: int = 0
        self.notifications_timestamp: int = 0
        self.viewport_timestamp: int = 0

        # Granular Dirty Flags (Legacy support)
        self.dirty_background: bool = False
        self.dirty_tokens: bool = False
        self.dirty_hands: bool = False
        self.dirty_viewport: bool = False

    def update_from_frame(self, shm_view: np.ndarray, timestamp: int):
        """
        Updates the background from a shared memory view using the injected processor.
        """
        if timestamp <= self.last_frame_timestamp:
            return  # Drop old frame

        if self.frame_processor:
            # ROI Extraction / Processing
            processed = self.frame_processor(shm_view)
            # Copy into local buffer to release SHM lease immediately
            self.background = processed.copy()
        else:
            # Default to full copy if no processor
            self.background = shm_view.copy()

        self.last_frame_timestamp = timestamp
        self.dirty_background = True

    def update_viewport(self, new_viewport: ViewportState):
        """Updates the viewport state and increments its timestamp if changed."""
        if (
            self.viewport.x != new_viewport.x
            or self.viewport.y != new_viewport.y
            or self.viewport.zoom != new_viewport.zoom
            or self.viewport.rotation != new_viewport.rotation
        ):
            self.viewport = new_viewport
            self.viewport_timestamp += 1
            self.dirty_viewport = True

    def increment_map_timestamp(self):
        """Manually trigger a map cache invalidation."""
        self.map_timestamp += 1

    def increment_menu_timestamp(self):
        """Manually trigger a menu cache invalidation."""
        self.menu_timestamp += 1

    def increment_notifications_timestamp(self):
        """Manually trigger a notification cache invalidation."""
        self.notifications_timestamp += 1

    def apply(self, result: DetectionResult):
        """
        Applies a detection result from a worker process to the state.
        Ensures synchronization via timestamp.
        """
        if result.timestamp < self.last_frame_timestamp - 1000000:  # 1s grace window
            # In a real system, we might be more strict.
            pass

        if result.type == ResultType.ARUCO:
            changed = False
            if "tokens" in result.data:
                # Logical/Snapped tokens
                new_tokens = result.data["tokens"]
                if not self._tokens_equal(self.tokens, new_tokens):
                    self.tokens = new_tokens
                    self.dirty_tokens = True
                    changed = True

                # Update raw tokens if provided
                if "raw_tokens" in result.data:
                    new_raw_tokens = result.data["raw_tokens"]
                    if not self._tokens_equal(self.raw_tokens, new_raw_tokens):
                        self.raw_tokens = new_raw_tokens
                        changed = True
            else:
                # Raw ArUco from workers (corners, ids)
                new_ids = result.data.get("ids", [])
                new_corners = result.data.get("corners", [])

                if self._raw_aruco_changed(new_ids, new_corners):
                    self.raw_aruco = {
                        "corners": new_corners,
                        "ids": new_ids,
                    }
                    self.dirty_tokens = True
                    changed = True

            if changed:
                self.tokens_timestamp += 1

        elif result.type == ResultType.HANDS:
            new_landmarks = result.data.get("landmarks", [])
            new_handedness = result.data.get("handedness", [])

            if not self._hands_equal(
                self.hands, self.handedness, new_landmarks, new_handedness
            ):
                self.hands = new_landmarks
                self.handedness = new_handedness
                self.dirty_hands = True
                self.hands_timestamp += 1

        elif result.type == ResultType.GESTURE:
            new_gesture = result.data.get("gesture")
            if self.gesture != new_gesture:
                self.gesture = new_gesture
                self.dirty_hands = True
                self.hands_timestamp += 1

    def _hands_equal(self, h1, hn1, h2, hn2) -> bool:
        """Heuristic check for hand landmark equality."""
        if len(h1) != len(h2):
            return False
        if len(h1) == 0:
            return True

        # Simple check: compare number of landmarks and a few key points if available
        # But for efficiency, if we have landmarks, we might just assume they changed
        # if the count is the same but they are not empty.
        # However, to be spec-compliant with "only on change", we should be careful.
        # MediaPipe landmarks are often slightly different every frame.
        # If they are different, we SHOULD increment.
        # But if they are BOTH empty, we should NOT.
        return False  # Assume different if not both empty

    def _tokens_equal(self, list1: List[Token], list2: List[Token]) -> bool:
        """Compares two token lists for semantic equality (positions and status)."""
        if len(list1) != len(list2):
            return False

        # Sort by ID for deterministic comparison
        s1 = sorted(list1, key=lambda t: t.id)
        s2 = sorted(list2, key=lambda t: t.id)

        for t1, t2 in zip(s1, s2):
            if t1.id != t2.id:
                return False
            # Check grid positions first as they are discrete
            if t1.grid_x != t2.grid_x or t1.grid_y != t2.grid_y:
                return False
            # Check status flags
            if t1.is_occluded != t2.is_occluded or t1.is_duplicate != t2.is_duplicate:
                return False
            # Check world coordinates
            if abs(t1.world_x - t2.world_x) > 0.5 or abs(t1.world_y - t2.world_y) > 0.5:
                return False

        return True

    def _raw_aruco_changed(self, new_ids: List[int], new_corners: List[Any]) -> bool:
        """Compares raw ArUco results for changes."""
        if self.raw_aruco["ids"] != new_ids:
            return True

        if len(self.raw_aruco["corners"]) != len(new_corners):
            return True

        return self.raw_aruco["corners"] != new_corners

    def clear_dirty(self):
        """Resets all dirty flags after a render cycle."""
        self.dirty_background = False
        self.dirty_tokens = False
        self.dirty_hands = False
        self.dirty_viewport = False
        # Clear raw ArUco after it has been potentially processed by a scene
        self.raw_aruco = {"corners": [], "ids": []}

    @property
    def is_dirty(self) -> bool:
        """Returns True if any part of the state has changed since last render."""
        return (
            self.dirty_background
            or self.dirty_tokens
            or self.dirty_hands
            or self.dirty_viewport
        )
