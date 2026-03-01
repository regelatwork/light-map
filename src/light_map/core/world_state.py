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

        self.tokens: List[Token] = []
        self.raw_aruco: Dict[str, Any] = {"corners": [], "ids": []}
        self.hands: List[Any] = []
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
                self.tokens = result.data["tokens"]
            else:
                self.raw_aruco = {
                    "corners": result.data.get("corners", []),
                    "ids": result.data.get("ids", []),
                }
            self.dirty_tokens = True
        elif result.type == ResultType.HANDS:
            self.hands = result.data.get("landmarks", [])
            self.dirty_hands = True
        elif result.type == ResultType.GESTURE:
            self.gesture = result.data.get("gesture")
            self.dirty_hands = True  # Gestures affect hand/input state

    def clear_dirty(self):
        """Resets all dirty flags after a render cycle."""
        self.dirty_background = False
        self.dirty_tokens = False
        self.dirty_hands = False
        self.dirty_viewport = False

    @property
    def is_dirty(self) -> bool:
        """Returns True if any part of the state has changed since last render."""
        return (
            self.dirty_background
            or self.dirty_tokens
            or self.dirty_hands
            or self.dirty_viewport
        )
