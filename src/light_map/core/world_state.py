import numpy as np
from typing import List, Optional, Callable, Any, Dict
from light_map.common_types import Token, DetectionResult, ResultType, ViewportState


class WorldState:
    """
    Central Data Repository (The "Source of Truth") for the MainProcess.
    Manages background frames, vision results, and dirty tracking.
    """

    def __init__(
        self, frame_processor: Optional[Callable[[np.ndarray], np.ndarray]] = None
    ):
        self.frame_processor = frame_processor

        # State Data
        self.background: Optional[np.ndarray] = None
        self.last_frame_timestamp: int = 0

        self.tokens: List[Token] = []  # Logical/Snapped tokens (Triggers dirty)
        self.raw_tokens: List[
            Token
        ] = []  # Live/Unsnapped tokens (Does NOT trigger dirty)
        self.raw_aruco: Dict[str, Any] = {"corners": [], "ids": []}
        self.hands: List[Any] = []  # Landmarks
        self.handedness: List[Any] = []
        self.gesture: Optional[str] = None
        self.viewport: ViewportState = ViewportState()

        # Granular Dirty Flags
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

    def apply(self, result: DetectionResult):
        """
        Applies a detection result from a worker process to the state.
        Ensures synchronization via timestamp.
        """
        if result.timestamp < self.last_frame_timestamp - 1000000:  # 1s grace window
            # In a real system, we might be more strict.
            # But results can be slightly behind the absolute latest frame.
            pass

        if result.type == ResultType.ARUCO:
            if "tokens" in result.data:
                # Logical/Snapped tokens
                new_tokens = result.data["tokens"]
                if not self._tokens_equal(self.tokens, new_tokens):
                    self.tokens = new_tokens
                    self.dirty_tokens = True

                # Update raw tokens if provided (they don't trigger dirty flag)
                if "raw_tokens" in result.data:
                    self.raw_tokens = result.data["raw_tokens"]
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

        elif result.type == ResultType.HANDS:
            self.hands = result.data.get("landmarks", [])
            self.handedness = result.data.get("handedness", [])
            self.dirty_hands = True
        elif result.type == ResultType.GESTURE:
            self.gesture = result.data.get("gesture")
            self.dirty_hands = True  # Gestures affect hand/input state

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
            # Check world coordinates ONLY if snapped coords didn't catch the change.
            # We use a 0.5 epsilon which means if the centroid moved more than
            # half a pixel/unit, we update. For SNAPPED tokens, this should
            # only trigger when they jump to a new grid cell.
            if abs(t1.world_x - t2.world_x) > 0.5 or abs(t1.world_y - t2.world_y) > 0.5:
                return False

        return True

    def _raw_aruco_changed(self, new_ids: List[int], new_corners: List[Any]) -> bool:
        """Compares raw ArUco results for changes."""
        if self.raw_aruco["ids"] != new_ids:
            return True

        if len(self.raw_aruco["corners"]) != len(new_corners):
            return True

        # For corners, we can just do a simple list equality check
        # as they are converted to lists in the worker.
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
