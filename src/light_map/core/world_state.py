import time
from contextlib import contextmanager
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
from light_map.core.token_merge_manager import TokenMergeManager
from .versioned_atom import VersionedAtom


class Transaction:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp

    def update(self, atom: VersionedAtom, new_value: Any):
        atom.update(new_value, force_timestamp=self.timestamp)


class WorldState:
    """
    Central Data Repository (The "Source of Truth") for the MainProcess.
    Manages background frames, vision results, and granular versioning for caching.
    """

    def __init__(
        self, frame_processor: Optional[Callable[[np.ndarray], np.ndarray]] = None
    ):
        self.frame_processor = frame_processor

        # State Data
        self.background: Optional[np.ndarray] = None
        self.last_frame_timestamp: int = 0

        # Atoms
        self._tokens_atom = VersionedAtom([], "tokens", equality_fn=self._tokens_equal)
        self._raw_tokens_atom = VersionedAtom([], "raw_tokens")
        self._blockers_atom = VersionedAtom([], "blockers")
        self._token_merge_manager = TokenMergeManager()
        
        self._raw_aruco_atom = VersionedAtom({"corners": [], "ids": []}, "raw_aruco", equality_fn=self._raw_aruco_equal)
        self._inputs_atom = VersionedAtom([], "inputs", equality_fn=self._inputs_equal)
        self._landmarks_atom = VersionedAtom([], "landmarks", equality_fn=self._landmarks_equal)
        self._handedness_atom = VersionedAtom([], "handedness")
        self._gesture_atom = VersionedAtom(None, "gesture")
        
        self._viewport_atom = VersionedAtom(ViewportState(), "viewport")
        self._menu_state_atom = VersionedAtom(None, "menu_state")
        self._system_time_atom = VersionedAtom(0.0, "system_time")
        
        self._scene_atom = VersionedAtom("", "scene")
        self._fow_atom = VersionedAtom(0, "fow")
        self._calibration_atom = VersionedAtom(0, "calibration")
        self._notifications_atom = VersionedAtom(0, "notifications")
        self._map_atom = VersionedAtom(0, "map")
        self._visibility_mask_atom = VersionedAtom(None, "visibility_mask", equality_fn=np.array_equal)
        self._show_tokens_atom = VersionedAtom(True, "show_tokens")

        self.fps: float = 0.0
        self.selection: SelectionState = SelectionState()
        self.dwell_state: Dict[str, Any] = {}
        self.summon_progress: float = 0.0

        # Grid Metadata
        self.grid_spacing_svg: float = 0.0
        self.grid_origin_svg_x: float = 0.0
        self.grid_origin_svg_y: float = 0.0

        # Remote Action Queuing
        self.pending_actions: List[Dict[str, Any]] = []

        # Hand Expiration tracking
        self.last_hand_timestamp: float = 0.0

    # Properties for Atoms

    @property
    def viewport(self) -> ViewportState:
        return self._viewport_atom.value

    @viewport.setter
    def viewport(self, value: ViewportState):
        self._viewport_atom.update(value)

    @property
    def menu_state(self) -> Optional[MenuState]:
        return self._menu_state_atom.value

    @menu_state.setter
    def menu_state(self, value: Optional[MenuState]):
        self._menu_state_atom.update(value)

    @property
    def tokens(self) -> List[Token]:
        return self._tokens_atom.value

    @tokens.setter
    def tokens(self, value: List[Token]):
        self._tokens_atom.update(value)

    @property
    def raw_tokens(self) -> List[Token]:
        return self._raw_tokens_atom.value

    @raw_tokens.setter
    def raw_tokens(self, value: List[Token]):
        self._raw_tokens_atom.update(value)

    @property
    def blockers(self) -> List[Dict[str, Any]]:
        return self._blockers_atom.value

    @blockers.setter
    def blockers(self, value: List[Dict[str, Any]]):
        self._blockers_atom.update(value)

    @property
    def system_time(self) -> float:
        return self._system_time_atom.value

    @system_time.setter
    def system_time(self, value: float):
        self._system_time_atom.update(value)

    @property
    def raw_aruco(self) -> Dict[str, Any]:
        return self._raw_aruco_atom.value

    @raw_aruco.setter
    def raw_aruco(self, value: Dict[str, Any]):
        self._raw_aruco_atom.update(value)

    @property
    def inputs(self) -> List[HandInput]:
        return self._inputs_atom.value

    @inputs.setter
    def inputs(self, value: List[HandInput]):
        self._inputs_atom.update(value)

    @property
    def hands(self) -> List[Any]:
        return self._landmarks_atom.value

    @hands.setter
    def hands(self, value: List[Any]):
        self._landmarks_atom.update(value)

    @property
    def handedness(self) -> List[Any]:
        return self._handedness_atom.value

    @handedness.setter
    def handedness(self, value: List[Any]):
        self._handedness_atom.update(value)

    @property
    def gesture(self) -> Optional[str]:
        return self._gesture_atom.value

    @gesture.setter
    def gesture(self, value: Optional[str]):
        self._gesture_atom.update(value)

    @property
    def current_scene_name(self) -> str:
        return self._scene_atom.value

    @current_scene_name.setter
    def current_scene_name(self, value: str):
        self._scene_atom.update(value)

    @property
    def visibility_mask(self) -> Optional[np.ndarray]:
        return self._visibility_mask_atom.value

    @visibility_mask.setter
    def visibility_mask(self, value: Optional[np.ndarray]):
        self._visibility_mask_atom.update(value)

    @property
    def effective_show_tokens(self) -> bool:
        return self._show_tokens_atom.value

    @effective_show_tokens.setter
    def effective_show_tokens(self, value: bool):
        self._show_tokens_atom.update(value)

    # Timestamps (Signal manual updates via setter)

    @property
    def map_timestamp(self) -> int:
        return self._map_atom.timestamp

    @map_timestamp.setter
    def map_timestamp(self, value: Any):
        # We use value increment or assignment as a signal to force-update timestamp
        current = self._map_atom.value
        if isinstance(current, int) and isinstance(value, int):
             self._map_atom.update(value, force_timestamp=time.monotonic_ns())
        else:
             self._map_atom.update(value, force_timestamp=time.monotonic_ns())

    @property
    def fow_timestamp(self) -> int:
        return self._fow_atom.timestamp

    @fow_timestamp.setter
    def fow_timestamp(self, value: Any):
        self._fow_atom.update(value, force_timestamp=time.monotonic_ns())

    @property
    def calibration_timestamp(self) -> int:
        return self._calibration_atom.timestamp

    @calibration_timestamp.setter
    def calibration_timestamp(self, value: Any):
        self._calibration_atom.update(value, force_timestamp=time.monotonic_ns())

    @property
    def notifications_timestamp(self) -> int:
        return self._notifications_atom.timestamp

    @notifications_timestamp.setter
    def notifications_timestamp(self, value: Any):
        self._notifications_atom.update(value, force_timestamp=time.monotonic_ns())

    @property
    def scene_timestamp(self) -> int:
        return self._scene_atom.timestamp

    @scene_timestamp.setter
    def scene_timestamp(self, value: Any):
        self._scene_atom.update(value, force_timestamp=time.monotonic_ns())

    @property
    def menu_timestamp(self) -> int:
        return self._menu_state_atom.timestamp

    @menu_timestamp.setter
    def menu_timestamp(self, value: Any):
        self._menu_state_atom.update(self._menu_state_atom.value, force_timestamp=time.monotonic_ns())

    @property
    def viewport_timestamp(self) -> int:
        return self._viewport_atom.timestamp

    @viewport_timestamp.setter
    def viewport_timestamp(self, value: Any):
        self._viewport_atom.update(self._viewport_atom.value, force_timestamp=time.monotonic_ns())

    @property
    def visibility_timestamp(self) -> int:
        return max(
            self._blockers_atom.timestamp,
            self._visibility_mask_atom.timestamp,
        )

    @visibility_timestamp.setter
    def visibility_timestamp(self, value: Any):
        self._visibility_mask_atom.update(self._visibility_mask_atom.value, force_timestamp=time.monotonic_ns())

    @property
    def map_version(self) -> int:
        return self.map_timestamp

    @map_version.setter
    def map_version(self, value: int):
        self.map_timestamp = value

    @property
    def fow_version(self) -> int:
        return self.fow_timestamp

    @fow_version.setter
    def fow_version(self, value: int):
        self.fow_timestamp = value

    @property
    def calibration_version(self) -> int:
        return self.calibration_timestamp

    @calibration_version.setter
    def calibration_version(self, value: int):
        self.calibration_timestamp = value

    @property
    def notifications_version(self) -> int:
        return self.notifications_timestamp

    @notifications_version.setter
    def notifications_version(self, value: int):
        self.notifications_timestamp = value

    @property
    def scene_version(self) -> int:
        return self.scene_timestamp

    @scene_version.setter
    def scene_version(self, value: int):
        self.scene_timestamp = value

    @property
    def menu_version(self) -> int:
        return self.menu_timestamp

    @menu_version.setter
    def menu_version(self, value: int):
        self.menu_timestamp = value

    @property
    def viewport_version(self) -> int:
        return self.viewport_timestamp

    @viewport_version.setter
    def viewport_version(self, value: int):
        self.viewport_timestamp = value

    @property
    def visibility_version(self) -> int:
        return self.visibility_timestamp

    @visibility_version.setter
    def visibility_version(self, value: int):
        self.visibility_timestamp = value

    @property
    def tokens_timestamp(self) -> int:
        return max(self._tokens_atom.timestamp, self._raw_tokens_atom.timestamp)

    @property
    def system_time_timestamp(self) -> int:
        return self._system_time_atom.timestamp

    @property
    def raw_aruco_timestamp(self) -> int:
        return self._raw_aruco_atom.timestamp

    @property
    def hands_timestamp(self) -> int:
        return max(
            self._inputs_atom.timestamp,
            self._landmarks_atom.timestamp,
            self._handedness_atom.timestamp,
            self._gesture_atom.timestamp,
        )

    # Methods

    @contextmanager
    def transaction(self):
        ts = time.monotonic_ns()
        yield Transaction(ts)

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
        """Updates the viewport state and increments its version if changed."""
        self.viewport = new_viewport

    def update_visibility_mask(self, mask: np.ndarray):
        """Updates the LOS visibility mask and increments version if changed."""
        self.visibility_mask = mask

    def update_menu_state(self, new_menu_state: Optional[MenuState]):
        """Updates the menu state and increments its version if changed."""
        self.menu_state = new_menu_state

    def update_performance_metrics(self, fps: float):
        """Updates the FPS metric. Does not trigger version increment as it's for transient display."""
        self.fps = fps

    def update_inputs(self, inputs: List[HandInput], current_time: float = 0.0):
        """Updates the standardized hand inputs and increments hands_timestamp if changed."""
        if inputs:
            self.last_hand_timestamp = current_time

        self.inputs = inputs

    def apply(self, result: DetectionResult, current_time: Optional[float] = None):
        """
        Applies a detection result from a worker process to the state.
        Ensures synchronization via timestamp.
        """
        if current_time is None:
            current_time = time.monotonic()

        if result.type == ResultType.ARUCO:
            if "tokens" in result.data:
                # Delegate merging to the manager
                if self._token_merge_manager.update_source(result):
                    self.tokens = self._token_merge_manager.get_merged_tokens()
                    self.raw_tokens = self._token_merge_manager.get_merged_raw_tokens()
            else:
                # Raw ArUco from workers (corners, ids)
                new_ids = result.data.get("ids", [])
                new_corners = result.data.get("corners", [])
                self.raw_aruco = {"ids": new_ids, "corners": new_corners}

        elif result.type == ResultType.HANDS:
            if (
                isinstance(result.data, list)
                and len(result.data) > 0
                and hasattr(result.data[0], "gesture")
            ):
                # Standardized HandInput objects (likely from Remote Driver)
                # BUG-FIX: Even if inputs didn't change, we MUST increment hands_timestamp
                # because scenes need to process time-based events (dwell, linger)
                # every frame that hands are present.
                self._inputs_atom.update(result.data, force_timestamp=time.monotonic_ns())
                self.last_hand_timestamp = current_time
            else:
                # Raw landmarks from MediaPipe worker
                new_landmarks = result.data.get("landmarks", [])
                new_handedness = result.data.get("handedness", [])

                # Update landmarks and handedness; they update their own timestamps if changed
                self.hands = new_landmarks
                self.handedness = new_handedness
                self.last_hand_timestamp = current_time

        elif result.type == ResultType.GESTURE:
            self.gesture = result.data.get("gesture")

        elif result.type == ResultType.ACTION:
            self.pending_actions.append(result.data)

    # Equality Helpers for Atoms

    def _inputs_equal(self, i1: List[HandInput], i2: List[HandInput]) -> bool:
        """Checks for semantic equality between two lists of hand inputs."""
        if len(i1) != len(i2):
            return False
        if len(i1) == 0:
            return True

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

    def _landmarks_equal(self, h1: List[Any], h2: List[Any]) -> bool:
        """Heuristic check for hand landmark equality."""
        if len(h1) != len(h2):
            return False
        if len(h1) == 0:
            return True
        # MediaPipe landmarks are often slightly different every frame.
        # Assume different if not both empty to trigger updates.
        return False

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
                if t1.grid_x != t2.grid_x or t1.grid_y != t2.grid_y:
                    return False
            else:
                if (
                    abs(t1.world_x - t2.world_x) > 1.0
                    or abs(t1.world_y - t2.world_y) > 1.0
                ):
                    return False

            if t1.is_occluded != t2.is_occluded or t1.is_duplicate != t2.is_duplicate:
                return False

        return True

    def _raw_aruco_equal(self, d1: Dict[str, Any], d2: Dict[str, Any]) -> bool:
        """Compares raw ArUco results for equality."""
        if d1["ids"] != d2["ids"]:
            return False

        if len(d1["corners"]) != len(d2["corners"]):
            return False

        for old_c, new_c in zip(d1["corners"], d2["corners"]):
            if not np.array_equal(old_c, new_c):
                return False

        return True

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
            "map_timestamp": self.map_timestamp,
            "menu_timestamp": self.menu_timestamp,
            "tokens_timestamp": self.tokens_timestamp,
            "raw_aruco_timestamp": self.raw_aruco_timestamp,
            "hands_timestamp": self.hands_timestamp,
            "scene_timestamp": self.scene_timestamp,
            "notifications_timestamp": self.notifications_timestamp,
            "viewport_timestamp": self.viewport_timestamp,
            "visibility_timestamp": self.visibility_timestamp,
            "fow_timestamp": self.fow_timestamp,
            "system_time": self.system_time,
            "system_time_timestamp": self.system_time_timestamp,
            "effective_show_tokens": self.effective_show_tokens,
        }

    def clear_raw_aruco(self):
        """Resets raw ArUco after it has been potentially processed by a scene."""
        self.raw_aruco = {"corners": [], "ids": []}
