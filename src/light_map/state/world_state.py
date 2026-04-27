import time
from contextlib import contextmanager
import numpy as np
from typing import List, Optional, Callable, Any, Dict, Set
from light_map.core.common_types import (
    Token,
    DetectionResult,
    ResultType,
    ViewportState,
    SelectionState,
    GridMetadata,
    MapRenderState,
    CalibrationState,
    ProjectorPose,
    GridType,
    CoverResult,
)
from light_map.menu.menu_system import MenuState
from light_map.core.scene import HandInput
from light_map.vision.processing.token_merge_manager import TokenMergeManager
from light_map.state.versioned_atom import VersionedAtom
from light_map.visibility.visibility_types import VisibilityBlocker


class Transaction:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp

    def update(self, atom: VersionedAtom, new_value: Any, force: bool = False):
        if force or atom.would_change(new_value):
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
        self._blockers_atom = VersionedAtom(
            [], "blockers", equality_fn=self._blockers_equal
        )
        self._token_merge_manager = TokenMergeManager()

        self._raw_aruco_atom = VersionedAtom(
            {"corners": [], "ids": []}, "raw_aruco", equality_fn=self._raw_aruco_equal
        )
        self._inputs_atom = VersionedAtom([], "inputs", equality_fn=self._inputs_equal)
        self._landmarks_atom = VersionedAtom(
            [], "landmarks", equality_fn=self._landmarks_equal
        )
        self._handedness_atom = VersionedAtom([], "handedness")
        self._gesture_atom = VersionedAtom(None, "gesture")

        self._viewport_atom = VersionedAtom(ViewportState(), "viewport")
        self._menu_state_atom = VersionedAtom(None, "menu_state")
        self._system_time_atom = VersionedAtom(0.0, "system_time")

        self._scene_atom = VersionedAtom("", "scene")
        self._scene_state_atom = VersionedAtom(0, "scene_state")
        self._fow_mask_atom = VersionedAtom(
            None, "fow_mask", equality_fn=np.array_equal
        )
        self._discovered_ids_atom = VersionedAtom(set(), "discovered_ids")
        self._fow_disabled_atom = VersionedAtom(False, "fow_disabled")
        self._calibration_atom = VersionedAtom(
            CalibrationState(), "calibration", equality_fn=self._calibration_equal
        )
        self._notifications_atom = VersionedAtom([], "notifications")
        self._map_render_state_atom = VersionedAtom(
            MapRenderState(), "map_render_state"
        )
        self._visibility_mask_atom = VersionedAtom(
            None, "visibility_mask", equality_fn=np.array_equal
        )
        self._inspected_token_mask_atom = VersionedAtom(
            None, "inspected_token_mask", equality_fn=np.array_equal
        )
        self._show_tokens_atom = VersionedAtom(True, "show_tokens")
        self._dwell_state_atom = VersionedAtom({}, "dwell_state")
        self._summon_progress_atom = VersionedAtom(0.0, "summon_progress")
        self._selection_atom = VersionedAtom(SelectionState(), "selection")
        self._inspected_token_id_atom = VersionedAtom(None, "inspected_token_id")
        self._tactical_bonuses_atom = VersionedAtom({}, "tactical_bonuses")
        self._grid_metadata_atom = VersionedAtom(GridMetadata(), "grid_metadata")
        self._projector_pose_atom = VersionedAtom(
            ProjectorPose(0.0, 0.0, 0.0), "projector_pose"
        )
        self._fps_atom = VersionedAtom(0.0, "fps")
        self._config_version_atom = VersionedAtom(0, "config")

        # Lifecycle
        self.is_running = True

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
    def blockers(self) -> List[VisibilityBlocker]:
        return self._blockers_atom.value

    @blockers.setter
    def blockers(self, value: List[VisibilityBlocker]):
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
    def scene_data(self) -> Any:
        return self._scene_state_atom.value

    @scene_data.setter
    def scene_data(self, value: Any):
        self._scene_state_atom.update(value)

    @property
    def map_render_state(self) -> MapRenderState:
        return self._map_render_state_atom.value

    @map_render_state.setter
    def map_render_state(self, value: MapRenderState):
        self._map_render_state_atom.update(value)

    @property
    def fow_mask(self) -> Optional[np.ndarray]:
        return self._fow_mask_atom.value

    @fow_mask.setter
    def fow_mask(self, value: Optional[np.ndarray]):
        self._fow_mask_atom.update(value)

    @property
    def discovered_ids(self) -> Set[str]:
        return self._discovered_ids_atom.value

    @discovered_ids.setter
    def discovered_ids(self, value: Set[str]):
        self._discovered_ids_atom.update(value)

    @property
    def fow_disabled(self) -> bool:
        return self._fow_disabled_atom.value

    @fow_disabled.setter
    def fow_disabled(self, value: bool):
        self._fow_disabled_atom.update(value)

    @property
    def scene_version(self) -> int:
        return max(
            self._scene_atom.timestamp,
            self._scene_state_atom.timestamp,
            self._calibration_atom.timestamp,
        )

    @property
    def map_version(self) -> int:
        return self._map_render_state_atom.timestamp

    @property
    def fow_version(self) -> int:
        return max(
            self._fow_mask_atom.timestamp,
            self._discovered_ids_atom.timestamp,
            self._fow_disabled_atom.timestamp,
        )

    @property
    def fow_disabled_version(self) -> int:
        return self._fow_disabled_atom.timestamp

    @property
    def visibility_version(self) -> int:
        return max(
            self._visibility_mask_atom.timestamp,
            self._inspected_token_mask_atom.timestamp,
            self._blockers_atom.timestamp,
        )

    @property
    def tokens_version(self) -> int:
        return max(self._tokens_atom.timestamp, self._raw_tokens_atom.timestamp)

    @property
    def notifications_version(self) -> int:
        return self._notifications_atom.timestamp

    @property
    def visibility_mask(self) -> Optional[np.ndarray]:
        return self._visibility_mask_atom.value

    @visibility_mask.setter
    def visibility_mask(self, value: Optional[np.ndarray]):
        self._visibility_mask_atom.update(value)

    @property
    def inspected_token_mask(self) -> Optional[np.ndarray]:
        return self._inspected_token_mask_atom.value

    @inspected_token_mask.setter
    def inspected_token_mask(self, value: Optional[np.ndarray]):
        self._inspected_token_mask_atom.update(value)

    @property
    def inspected_token_mask_version(self) -> int:
        return self._inspected_token_mask_atom.timestamp

    @property
    def effective_show_tokens(self) -> bool:
        return self._show_tokens_atom.value

    @effective_show_tokens.setter
    def effective_show_tokens(self, value: bool):
        self._show_tokens_atom.update(value)

    @property
    def dwell_state(self) -> Dict[str, Any]:
        return self._dwell_state_atom.value

    @dwell_state.setter
    def dwell_state(self, value: Dict[str, Any]):
        self._dwell_state_atom.update(value)

    @property
    def summon_progress(self) -> float:
        return self._summon_progress_atom.value

    @summon_progress.setter
    def summon_progress(self, value: float):
        self._summon_progress_atom.update(value)

    @property
    def selection(self) -> SelectionState:
        return self._selection_atom.value

    @selection.setter
    def selection(self, value: SelectionState):
        self._selection_atom.update(value)

    @property
    def inspected_token_id(self) -> Optional[int]:
        return self._inspected_token_id_atom.value

    @inspected_token_id.setter
    def inspected_token_id(self, value: Optional[int]):
        self._inspected_token_id_atom.update(value)

    @property
    def inspected_token_id_version(self) -> int:
        return self._inspected_token_id_atom.timestamp

    @property
    def tactical_bonuses(self) -> Dict[int, CoverResult]:
        return self._tactical_bonuses_atom.value

    @tactical_bonuses.setter
    def tactical_bonuses(self, value: Dict[int, CoverResult]):
        self._tactical_bonuses_atom.update(value)

    @property
    def tactical_bonuses_version(self) -> int:
        return self._tactical_bonuses_atom.timestamp

    @property
    def config_version(self) -> int:
        return self._config_version_atom.timestamp

    @property
    def config_data(self) -> int:
        return self._config_version_atom.value

    @config_data.setter
    def config_data(self, value: int):
        self._config_version_atom.update(value)

    @property
    def projector_pose(self) -> ProjectorPose:
        return self._projector_pose_atom.value

    @projector_pose.setter
    def projector_pose(self, value: ProjectorPose):
        self._projector_pose_atom.update(value)

    @property
    def grid_metadata(self) -> GridMetadata:
        return self._grid_metadata_atom.value

    @grid_metadata.setter
    def grid_metadata(self, value: GridMetadata):
        self._grid_metadata_atom.update(value)

    @property
    def grid_type(self) -> GridType:
        return self._grid_metadata_atom.value.type

    @grid_type.setter
    def grid_type(self, value: GridType):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=current.spacing_svg,
                origin_svg_x=current.origin_svg_x,
                origin_svg_y=current.origin_svg_y,
                type=value,
                overlay_visible=current.overlay_visible,
                overlay_color=current.overlay_color,
            )
        )

    @property
    def grid_overlay_visible(self) -> bool:
        return self._grid_metadata_atom.value.overlay_visible

    @grid_overlay_visible.setter
    def grid_overlay_visible(self, value: bool):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=current.spacing_svg,
                origin_svg_x=current.origin_svg_x,
                origin_svg_y=current.origin_svg_y,
                type=current.type,
                overlay_visible=value,
                overlay_color=current.overlay_color,
            )
        )

    @property
    def grid_overlay_color(self) -> str:
        return self._grid_metadata_atom.value.overlay_color

    @grid_overlay_color.setter
    def grid_overlay_color(self, value: str):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=current.spacing_svg,
                origin_svg_x=current.origin_svg_x,
                origin_svg_y=current.origin_svg_y,
                type=current.type,
                overlay_visible=current.overlay_visible,
                overlay_color=value,
            )
        )

    @property
    def calibration(self) -> Any:
        return self._calibration_atom.value

    @calibration.setter
    def calibration(self, value: Any):
        self._calibration_atom.update(value)

    @property
    def grid_spacing_svg(self) -> float:
        return self._grid_metadata_atom.value.spacing_svg

    @grid_spacing_svg.setter
    def grid_spacing_svg(self, value: float):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=value,
                origin_svg_x=current.origin_svg_x,
                origin_svg_y=current.origin_svg_y,
                type=current.type,
                overlay_visible=current.overlay_visible,
                overlay_color=current.overlay_color,
            )
        )

    @property
    def grid_origin_svg_x(self) -> float:
        return self._grid_metadata_atom.value.origin_svg_x

    @grid_origin_svg_x.setter
    def grid_origin_svg_x(self, value: float):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=current.spacing_svg,
                origin_svg_x=value,
                origin_svg_y=current.origin_svg_y,
                type=current.type,
                overlay_visible=current.overlay_visible,
                overlay_color=current.overlay_color,
            )
        )

    @property
    def grid_origin_svg_y(self) -> float:
        return self._grid_metadata_atom.value.origin_svg_y

    @grid_origin_svg_y.setter
    def grid_origin_svg_y(self, value: float):
        current = self._grid_metadata_atom.value
        self._grid_metadata_atom.update(
            GridMetadata(
                spacing_svg=current.spacing_svg,
                origin_svg_x=current.origin_svg_x,
                origin_svg_y=value,
                type=current.type,
                overlay_visible=current.overlay_visible,
                overlay_color=current.overlay_color,
            )
        )

    # Versions (Signal manual updates via atom.update)

    @property
    def menu_version(self) -> int:
        return self._menu_state_atom.timestamp

    @property
    def viewport_version(self) -> int:
        return self._viewport_atom.timestamp

    @property
    def calibration_version(self) -> int:
        return self._calibration_atom.timestamp

    @property
    def system_time_version(self) -> int:
        return self._system_time_atom.timestamp

    @property
    def dwell_state_version(self) -> int:
        return self._dwell_state_atom.timestamp

    @property
    def summon_progress_version(self) -> int:
        return self._summon_progress_atom.timestamp

    @property
    def tactical_version(self) -> int:
        return self._tactical_bonuses_atom.timestamp

    @property
    def selection_version(self) -> int:
        return self._selection_atom.timestamp

    @property
    def inspected_token_version(self) -> int:
        return self._inspected_token_id_atom.timestamp

    @property
    def projector_pose_version(self) -> int:
        return self._projector_pose_atom.timestamp

    @property
    def grid_metadata_version(self) -> int:
        return self._grid_metadata_atom.timestamp

    @property
    def raw_aruco_version(self) -> int:
        return self._raw_aruco_atom.timestamp

    @property
    def hands_version(self) -> int:
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

    @property
    def fps(self) -> float:
        return self._fps_atom.value

    @property
    def fps_version(self) -> int:
        return self._fps_atom.timestamp

    def update_performance_metrics(self, fps: float):
        """Updates the FPS metric and triggers a version update."""
        self._fps_atom.update(fps)

    def update_inputs(self, inputs: List[HandInput], current_time: float = 0.0):
        """Updates the standardized hand inputs and increments hands_version if changed."""
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

        with self.transaction() as tx:
            if result.type == ResultType.ARUCO:
                if "tokens" in result.data:
                    # Delegate merging to the manager
                    if self._token_merge_manager.update_source(result):
                        tx.update(
                            self._tokens_atom,
                            self._token_merge_manager.get_merged_tokens(),
                        )
                        tx.update(
                            self._raw_tokens_atom,
                            self._token_merge_manager.get_merged_raw_tokens(),
                        )
                else:
                    # Raw ArUco from workers (corners, ids)
                    new_ids = result.data.get("ids", [])
                    new_corners = result.data.get("corners", [])
                    tx.update(
                        self._raw_aruco_atom, {"ids": new_ids, "corners": new_corners}
                    )

            elif result.type == ResultType.HANDS:
                if (
                    isinstance(result.data, list)
                    and len(result.data) > 0
                    and hasattr(result.data[0], "gesture")
                ):
                    tx.update(self._inputs_atom, result.data, force=True)
                    self.last_hand_timestamp = current_time
                else:
                    # Raw landmarks from MediaPipe worker
                    new_landmarks = result.data.get("landmarks", [])
                    new_handedness = result.data.get("handedness", [])

                    # Update landmarks and handedness; they update their own timestamps if changed
                    tx.update(self._landmarks_atom, new_landmarks)
                    tx.update(self._handedness_atom, new_handedness)
                    self.last_hand_timestamp = current_time

            elif result.type == ResultType.GESTURE:
                tx.update(self._gesture_atom, result.data.get("gesture"))

            elif result.type == ResultType.ACTION:
                self.pending_actions.append(result.data)

    # Equality Helpers for Atoms

    def _calibration_equal(self, c1: CalibrationState, c2: CalibrationState) -> bool:
        """Correctly compares CalibrationState objects, handling numpy array fields."""
        if not isinstance(c1, CalibrationState) or not isinstance(c2, CalibrationState):
            return c1 == c2

        # Basic Fields
        if (
            c1.stage != c2.stage
            or c1.target_status != c2.target_status
            or c1.target_info != c2.target_info
            or c1.reprojection_error != c2.reprojection_error
            or c1.animation_start_times != c2.animation_start_times
            or c1.last_camera_frame_ts != c2.last_camera_frame_ts
            or c1.captured_count != c2.captured_count
            or c1.total_required != c2.total_required
            or c1.candidate_ppi != c2.candidate_ppi
            or c1.step_index != c2.step_index
            or c1.flash_intensity != c2.flash_intensity
            or c1.instruction_text != c2.instruction_text
            or c1.instruction_pos != c2.instruction_pos
        ):
            return False

        # Numpy Array Fields
        if not np.array_equal(c1.pattern_image, c2.pattern_image):
            return False
        if not np.array_equal(c1.object_points, c2.object_points):
            return False
        if not np.array_equal(c1.image_points, c2.image_points):
            return False
        if not np.array_equal(c1.rotation_vector, c2.rotation_vector):
            return False
        if not np.array_equal(c1.translation_vector, c2.translation_vector):
            return False

        return True

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

    def _blockers_equal(
        self, b1: List[VisibilityBlocker], b2: List[VisibilityBlocker]
    ) -> bool:
        """Checks if two lists of blockers are semantically equal."""
        if len(b1) != len(b2):
            return False

        if b1 is b2:
            return False

        for blocker1, blocker2 in zip(b1, b2):
            if (
                blocker1.id != blocker2.id
                or blocker1.is_open != blocker2.is_open
                or blocker1.type != blocker2.type
                or len(blocker1.points) != len(blocker2.points)
            ):
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
            "blockers": [
                {
                    "id": b.id,
                    "type": str(b.type),
                    "is_open": b.is_open,
                    "points": b.points,
                }
                for b in self.blockers
            ],
            "dwell_state": self.dwell_state,
            "summon_progress": self.summon_progress,
            "inspected_token_id": self.inspected_token_id,
            "grid_spacing_svg": self.grid_spacing_svg,
            "grid_origin_svg_x": self.grid_origin_svg_x,
            "grid_origin_svg_y": self.grid_origin_svg_y,
            "grid_type": str(self.grid_type),
            "grid_overlay_visible": self.grid_overlay_visible,
            "grid_overlay_color": self.grid_overlay_color,
            "grid_metadata": {
                "spacing_svg": self.grid_spacing_svg,
                "origin_svg_x": self.grid_origin_svg_x,
                "origin_svg_y": self.grid_origin_svg_y,
                "type": str(self.grid_type),
                "overlay_visible": self.grid_overlay_visible,
                "overlay_color": self.grid_overlay_color,
            },
            "map_version": self.map_version,
            "menu_version": self.menu_version,
            "tokens_version": self.tokens_version,
            "raw_aruco_version": self.raw_aruco_version,
            "hands_version": self.hands_version,
            "scene_version": self.scene_version,
            "notifications_version": self.notifications_version,
            "viewport_version": self.viewport_version,
            "visibility_version": self.visibility_version,
            "fow_version": self.fow_version,
            "dwell_state_version": self.dwell_state_version,
            "summon_progress_version": self.summon_progress_version,
            "selection_version": self.selection_version,
            "inspected_token_version": self.inspected_token_version,
            "projector_pose_version": self.projector_pose_version,
            "grid_metadata_version": self.grid_metadata_version,
            "system_time": self.system_time,
            "system_time_version": self.system_time_version,
            "effective_show_tokens": self.effective_show_tokens,
            "projector_pose": self.projector_pose.to_list(),
        }

    def clear_raw_aruco(self):
        """Resets raw ArUco after it has been potentially processed by a scene."""
        self.raw_aruco = {"corners": [], "ids": []}
