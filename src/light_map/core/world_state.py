import time
import numpy as np
from typing import List, Optional, Callable, Any, Dict
from light_map.common_types import (
    Token,
    DetectionResult,
    ResultType,
    ViewportState,
    SelectionState,
)
from light_map.menu_system import MenuState
from light_map.core.scene import HandInput


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
        self.menu_state: Optional[MenuState] = None
        self.inputs: List[HandInput] = []
        self.fps: float = 0.0
        self.current_scene_name: str = ""
        self.effective_show_tokens: bool = True
        self.visibility_mask: Optional[np.ndarray] = None
        self.selection: SelectionState = SelectionState()
        self.blockers: List[Dict[str, Any]] = []
        self.dwell_state: Dict[str, Any] = {}

        # Grid Metadata
        self.grid_spacing_svg: float = 0.0
        self.grid_origin_svg_x: float = 0.0
        self.grid_origin_svg_y: float = 0.0

        # Remote Action Queuing
        self.pending_actions: List[Dict[str, Any]] = []

        # Granular Timestamps (Monotonic counters for caching)
        self.map_timestamp: int = 0
        self.menu_timestamp: int = 0
        self.tokens_timestamp: int = 0
        self.hands_timestamp: int = 0
        self.scene_timestamp: int = 0
        self.notifications_timestamp: int = 0
        self.viewport_timestamp: int = 0
        self.visibility_timestamp: int = 0
        self.fow_timestamp: int = 0

        # Hand Expiration tracking
        self.last_hand_timestamp: float = 0.0

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

    def update_visibility_mask(self, mask: np.ndarray):
        """Updates the LOS visibility mask and increments timestamp if changed."""
        if self.visibility_mask is None or not np.array_equal(
            self.visibility_mask, mask
        ):
            self.visibility_mask = mask.copy()
            self.visibility_timestamp += 1

    def increment_map_timestamp(self):
        """Manually trigger a map cache invalidation."""
        self.map_timestamp += 1

    def increment_menu_timestamp(self):
        """Manually trigger a menu cache invalidation."""
        self.menu_timestamp += 1

    def increment_scene_timestamp(self):
        """Manually trigger a scene cache invalidation."""
        self.scene_timestamp += 1

    def update_menu_state(self, new_menu_state: Optional[MenuState]):
        """Updates the menu state and increments its timestamp if changed."""
        if self.menu_state != new_menu_state:
            self.menu_state = new_menu_state
            self.menu_timestamp += 1

    def increment_notifications_timestamp(self):
        """Manually trigger a notification cache invalidation."""
        self.notifications_timestamp += 1

    def increment_fow_timestamp(self):
        """Manually trigger a Fog of War cache invalidation."""
        self.fow_timestamp += 1

    def update_performance_metrics(self, fps: float):
        """Updates the FPS metric. Does not trigger dirty flag or timestamp as it's for transient display."""
        self.fps = fps

    def update_inputs(self, inputs: List[HandInput], current_time: float = 0.0):
        """Updates the standardized hand inputs and increments hands_timestamp if changed."""
        if inputs:
            self.last_hand_timestamp = current_time

        if not self._inputs_equal(self.inputs, inputs):
            self.inputs = inputs
            self.hands_timestamp += 1

    def _inputs_equal(self, i1: List[HandInput], i2: List[HandInput]) -> bool:
        """Checks for semantic equality between two lists of hand inputs."""
        if len(i1) != len(i2):
            return False
        if len(i1) == 0:
            return True

        # For simplicity, if they are not empty and lengths are same,
        # check gestures, positions and direction (with tolerance)
        for h1, h2 in zip(i1, i2):
            if h1.gesture != h2.gesture:
                return False
            if h1.proj_pos != h2.proj_pos:
                return False

            # Check direction vector change
            d1 = h1.unit_direction
            d2 = h2.unit_direction
            if abs(d1[0] - d2[0]) > 0.01 or abs(d1[1] - d2[1]) > 0.01:
                return False
        return True

    def apply(self, result: DetectionResult, current_time: Optional[float] = None):
        """
        Applies a detection result from a worker process to the state.
        Ensures synchronization via timestamp.
        """
        if current_time is None:
            current_time = time.monotonic()

        if result.type == ResultType.ARUCO:
            changed = False
            if "tokens" in result.data:
                # Logical/Snapped tokens
                new_tokens = result.data["tokens"]

                if not self._tokens_equal(self.tokens, new_tokens):
                    self.tokens = new_tokens
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
                    changed = True

            if changed:
                self.tokens_timestamp += 1

        elif result.type == ResultType.HANDS:
            if (
                isinstance(result.data, list)
                and len(result.data) > 0
                and hasattr(result.data[0], "gesture")
            ):
                # Standardized HandInput objects (likely from Remote Driver)
                if not self._inputs_equal(self.inputs, result.data):
                    self.inputs = result.data
                    self.hands_timestamp += 1

                # BUG-FIX: Even if inputs didn't change, we MUST increment hands_timestamp
                # because scenes need to process time-based events (dwell, linger)
                # every frame that hands are present.
                self.hands_timestamp += 1
                # Update timestamp to prevent immediate expiration
                self.last_hand_timestamp = current_time
            else:
                # Raw landmarks from MediaPipe worker
                new_landmarks = result.data.get("landmarks", [])
                new_handedness = result.data.get("handedness", [])

                if not self._hands_equal(
                    self.hands, self.handedness, new_landmarks, new_handedness
                ):
                    self.hands = new_landmarks
                    self.handedness = new_handedness
                    self.hands_timestamp += 1
                    # Update timestamp for raw landmarks too
                    self.last_hand_timestamp = current_time

        elif result.type == ResultType.GESTURE:
            new_gesture = result.data.get("gesture")
            if self.gesture != new_gesture:
                self.gesture = new_gesture
                self.hands_timestamp += 1

        elif result.type == ResultType.ACTION:
            self.pending_actions.append(result.data)

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

            # Use Grid Snapping if available (Stable against noise)
            if t1.grid_x is not None and t2.grid_x is not None:
                # If grid coordinates are assigned, ANY change in grid position is a semantic move.
                if t1.grid_x != t2.grid_x or t1.grid_y != t2.grid_y:
                    return False
            else:
                # If no grid, fall back to world coordinates with a 1.0 unit tolerance (usually mm)
                # to avoid floating point jitter from vision/camera noise triggering re-renders.
                if (
                    abs(t1.world_x - t2.world_x) > 1.0
                    or abs(t1.world_y - t2.world_y) > 1.0
                ):
                    return False

            # Check status flags
            if t1.is_occluded != t2.is_occluded or t1.is_duplicate != t2.is_duplicate:
                return False

        return True

    def _raw_aruco_changed(self, new_ids: List[int], new_corners: List[Any]) -> bool:
        """Compares raw ArUco results for changes."""
        if self.raw_aruco["ids"] != new_ids:
            return True

        if len(self.raw_aruco["corners"]) != len(new_corners):
            return True

        return self.raw_aruco["corners"] != new_corners

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the WorldState into a dictionary for the Remote Driver."""
        return {
            "scene": self.current_scene_name,
            "viewport": self.viewport.to_dict(),
            "fps": round(self.fps, 2),
            "tokens_count": len(self.tokens),
            "hands_count": len(self.inputs),
            "timestamp": self.last_frame_timestamp,
            "last_hand_timestamp": self.last_hand_timestamp,
            "selection": {
                "type": str(self.selection.type),
                "id": self.selection.id,
            },
            "blockers": self.blockers,
            "dwell_state": self.dwell_state,
            "grid_spacing_svg": self.grid_spacing_svg,
            "grid_origin_svg_x": self.grid_origin_svg_x,
            "grid_origin_svg_y": self.grid_origin_svg_y,
            "visibility_timestamp": self.visibility_timestamp,
        }

    def clear_raw_aruco(self):
        """Resets raw ArUco after it has been potentially processed by a scene."""
        self.raw_aruco = {"corners": [], "ids": []}
