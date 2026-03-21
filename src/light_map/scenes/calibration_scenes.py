from __future__ import annotations
import time
import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import math
import numpy as np
import os
from collections import Counter
import cv2
from light_map.display_utils import draw_text_with_background

from light_map.core.scene import Scene, SceneTransition
from light_map.core.map_interaction import MapInteractionController
from light_map.gestures import GestureType
from light_map.token_tracker import TokenTracker
from light_map.calibration_logic import calculate_ppi_from_frame, calibrate_extrinsics
from light_map.common_types import SceneId, Action, AppConfig, TimerKey
from light_map.calibration import (
    process_chessboard_images,
    save_camera_calibration,
    save_camera_extrinsics,
)

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput
    from light_map.interactive_app import InteractiveApp
    from light_map.common_types import Layer


class FlashCalibStage(Enum):
    START = auto()
    TESTING = auto()
    ANALYZING = auto()
    SHOW_RESULT = auto()
    DONE = auto()


class FlashCalibrationScene(Scene):
    """Handles the flash calibration sequence."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.token_tracker = TokenTracker()
        self._stage = FlashCalibStage.START
        self._test_levels = [255, 225, 195, 165, 135, 105, 75, 45]
        self._current_level_idx = 0
        self._results: Dict[int, int] = {}
        self._capture_frame = False
        self.is_dynamic = True

    def on_enter(self, payload: dict | None = None) -> None:
        self._stage = FlashCalibStage.START
        self._current_level_idx = 0
        self._results = {}
        self.token_tracker.debug_mode = self.context.debug_mode
        self.increment_version()
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == FlashCalibStage.START:
            self._change_stage(FlashCalibStage.TESTING, current_time)

        elif self._stage == FlashCalibStage.ANALYZING:
            self._analyze_results()
            self._change_stage(FlashCalibStage.SHOW_RESULT, current_time)

        elif self._stage == FlashCalibStage.DONE:
            return SceneTransition(SceneId.MENU)

        return None

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Calibration scenes only need standard scene + UI layers."""
        return self.get_scene_with_ui_stack(app)

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._stage == FlashCalibStage.TESTING:
            if self._capture_frame and self.context.last_camera_frame is not None:
                intensity = self._test_levels[self._current_level_idx]
                tokens = self.token_tracker.detect_tokens(
                    frame_white=self.context.last_camera_frame,
                    projector_matrix=self.context.app_config.projector_matrix,
                    map_system=self.context.map_system,
                    default_height_mm=0.0,  # Calibrate against table surface
                )
                self._results[intensity] = len(tokens)
                logging.info(
                    "Calibration: Level %d -> Found %d tokens", intensity, len(tokens)
                )
                self._capture_frame = False
                self._current_level_idx += 1

                if self._current_level_idx >= len(self._test_levels):
                    self._change_stage(FlashCalibStage.ANALYZING, time.monotonic())
                else:
                    # Next level's settle time is handled by _change_stage
                    self._change_stage(FlashCalibStage.TESTING, time.monotonic())

            # Display current flash level
            if self._current_level_idx < len(self._test_levels):
                intensity = self._test_levels[self._current_level_idx]
                return np.full_like(frame, intensity, dtype=np.uint8)

        if self._stage == FlashCalibStage.SHOW_RESULT:
            # The main app loop should handle rendering overlays. For now, this scene
            # doesn't modify the frame, it just lets the main loop show the map.
            return frame

        return np.zeros_like(frame, dtype=np.uint8)

    def _analyze_results(self):
        non_zero_results = {i: c for i, c in self._results.items() if c > 0}

        if not non_zero_results:
            optimal_intensity = 128  # Fallback
            msg = "Calibration failed: no tokens found."
        else:
            counts = list(non_zero_results.values())
            most_common_count = Counter(counts).most_common(1)[0][0]
            stable_intensities = [
                i for i, c in non_zero_results.items() if c == most_common_count
            ]
            stable_intensities.sort()
            # Pick the median of the stable intensities
            optimal_intensity = stable_intensities[len(stable_intensities) // 2]
            msg = f"Optimal intensity found: {optimal_intensity}"

        self.context.map_config_manager.set_flash_intensity(optimal_intensity)
        self.context.notifications.add_notification(msg)
        logging.info(msg)

    def _on_calibration_timer_expired(self):
        """Callback for when a calibration stage timer finishes."""
        current_time = self.context.time_provider()

        if self._stage == FlashCalibStage.TESTING:
            self._capture_frame = True  # Signal render() to process a frame

        elif self._stage == FlashCalibStage.SHOW_RESULT:
            self._change_stage(FlashCalibStage.DONE, current_time)

    def _change_stage(self, new_stage: FlashCalibStage, current_time: float):
        """Transitions to a new stage and schedules next steps if necessary."""
        self._stage = new_stage

        # Schedule future transitions
        delay = 0.0
        if self._stage == FlashCalibStage.TESTING:
            delay = 1.5
        elif self._stage == FlashCalibStage.SHOW_RESULT:
            delay = 2.0

        if delay > 0:
            self.context.events.schedule(
                delay,
                self._on_calibration_timer_expired,
                key=TimerKey.CALIBRATION_STAGE,
            )


class IntrinsicsCalibrationScene(Scene):
    """Handles camera intrinsics calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._captured_images: list[np.ndarray] = []
        self._stage = "CAPTURE"  # CAPTURE | PROCESSING | DONE | ERROR
        self._required_images = 15
        self.is_dynamic = True

    def on_enter(self, payload: Any = None) -> None:
        self._captured_images = []
        self._stage = "CAPTURE"
        self.increment_version()
        self.context.notifications.add_notification(
            f"Capture {self._required_images} chessboard images."
        )

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == "CAPTURE":
            if inputs and inputs[0].gesture == GestureType.CLOSED_FIST:
                # Capture image
                frame = self.context.last_camera_frame
                if frame is not None:
                    self._captured_images.append(frame)
                    self.context.notifications.add_notification(
                        f"Captured image {len(self._captured_images)}/{self._required_images}"
                    )
                    if len(self._captured_images) >= self._required_images:
                        self._stage = "PROCESSING"
                        self.context.notifications.add_notification(
                            "Processing chessboard images..."
                        )
                else:
                    self.context.notifications.add_notification(
                        "Error: Camera not available for calibration."
                    )

        elif self._stage == "PROCESSING":
            calibration_result = process_chessboard_images(self._captured_images)

            if calibration_result:
                (camera_matrix, distortion_coefficients), _ = calibration_result
                storage = self.context.app_config.storage_manager
                output_file = (
                    storage.get_data_path("camera_calibration.npz")
                    if storage
                    else "camera_calibration.npz"
                )
                save_camera_calibration(
                    camera_matrix, distortion_coefficients, output_file=output_file
                )
                self.context.notifications.add_notification(
                    "Camera calibrated successfully."
                )
                self._stage = "DONE"
                return SceneTransition(SceneId.MENU)
            else:
                self.context.notifications.add_notification(
                    "Camera calibration failed. Ensure target is visible and well-lit."
                )
                self._stage = "ERROR"
                return SceneTransition(SceneId.MENU)

        elif self._stage == "DONE" or self._stage == "ERROR":
            return SceneTransition(SceneId.MENU)

        return None

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Calibration scenes only need standard scene + UI layers."""
        return self.get_scene_with_ui_stack(app)

    def render(self, frame: np.ndarray) -> np.ndarray:
        # Overlay instructions or status based on stage
        if self._stage == "CAPTURE":
            text = f"Capture {len(self._captured_images)}/{self._required_images} images (Fist)"
            draw_text_with_background(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
        elif self._stage == "PROCESSING":
            text = "Processing..."
            draw_text_with_background(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2
            )
        elif self._stage == "DONE":
            text = "Calibration Complete! Returning to Menu."
            draw_text_with_background(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
        elif self._stage == "ERROR":
            text = "Calibration Failed! Returning to Menu."
            draw_text_with_background(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
            )

        return frame


class ProjectorCalibrationScene(Scene):
    """Handles projector calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "DISPLAY_PATTERN"  # DISPLAY_PATTERN | SETTLE | CAPTURE | PROCESSING | DONE | ERROR
        self._pattern_image: Optional[np.ndarray] = None
        self._pattern_params: Optional[Dict] = None
        self.is_dynamic = True

    def on_enter(self, payload: Any = None) -> None:
        from light_map.projector import generate_calibration_pattern

        self._stage = "DISPLAY_PATTERN"
        self.increment_version()

        # Generate pattern
        w, h = self.context.app_config.width, self.context.app_config.height
        self._pattern_image, self._pattern_params = generate_calibration_pattern(
            w, h, pattern_rows=13, pattern_cols=18, border_size=30
        )
        self.context.notifications.add_notification("Projecting calibration pattern...")
        self._change_stage("DISPLAY_PATTERN", self.context.time_provider())

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == "CAPTURE":
            frame = self.context.last_camera_frame
            if frame is not None:
                self._change_stage("PROCESSING", current_time)
                from light_map.projector import compute_projector_homography

                try:
                    matrix, cam_pts, proj_pts = compute_projector_homography(
                        frame, self._pattern_params
                    )

                    # Save results
                    storage = self.context.app_config.storage_manager
                    output_file = (
                        storage.get_data_path("projector_calibration.npz")
                        if storage
                        else "projector_calibration.npz"
                    )
                    np.savez(
                        output_file,
                        projector_matrix=matrix,
                        camera_points=cam_pts,
                        projector_points=proj_pts,
                        resolution=np.array([frame.shape[1], frame.shape[0]]),
                        camera_resolution=np.array([frame.shape[1], frame.shape[0]]),
                        projector_resolution=np.array(
                            [
                                self.context.app_config.width,
                                self.context.app_config.height,
                            ]
                        ),
                    )
                    # Update context
                    self.context.app_config.projector_matrix = matrix
                    self.context.notifications.add_notification(
                        "Projector calibrated successfully."
                    )
                    self._stage = "DONE"
                    return SceneTransition(SceneId.MENU)
                except Exception as e:
                    logging.error("Homography error: %s", e)
                    self.context.notifications.add_notification(
                        f"Calibration failed: {e}"
                    )
                    self._stage = "ERROR"
            else:
                self.context.notifications.add_notification(
                    "Error: No camera frame captured."
                )
                self._stage = "ERROR"

        if self._stage == "ERROR":
            return SceneTransition(SceneId.MENU)

        return None

    def _on_calibration_timer_expired(self):
        """Callback for when a calibration stage timer finishes."""
        current_time = self.context.time_provider()

        if self._stage == "DISPLAY_PATTERN":
            self._change_stage("SETTLE", current_time)

        elif self._stage == "SETTLE":
            self._change_stage("CAPTURE", current_time)

    def _change_stage(self, new_stage: str, current_time: float):
        """Transitions to a new stage and schedules next steps if necessary."""
        self._stage = new_stage

        # Schedule future transitions
        delay = 0.0
        if self._stage == "DISPLAY_PATTERN":
            delay = 1.0
        elif self._stage == "SETTLE":
            delay = 2.0

        if delay > 0:
            self.context.events.schedule(
                delay,
                self._on_calibration_timer_expired,
                key=TimerKey.CALIBRATION_STAGE,
            )

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """
        Calibration scenes only need standard scene + UI layers.
        We exclude notification and debug layers to avoid pattern interference.
        """
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.cursor_layer,
        ]

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._pattern_image is not None:
            return self._pattern_image
        return np.zeros_like(frame)


class ExtrinsicsCalibrationScene(Scene):
    """Handles camera extrinsics calibration (Camera Pose)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "PLACEMENT"  # PLACEMENT | CAPTURE | VERIFY | DONE | ERROR
        self._target_zones: List[Tuple[int, int, int]] = []  # x, y, suggested_id
        self._detected_ids: Dict[int, Tuple[float, float]] = {}  # id -> (u, v) cam
        self._known_targets: Dict[int, Tuple[float, float]] = {}  # id -> (px, py) proj
        self._ppi = 0.0
        self._rotation_vector: Optional[np.ndarray] = None
        self._translation_vector: Optional[np.ndarray] = None
        self._token_heights: Dict[int, float] = {}
        self._token_sizes: Dict[int, int] = {}
        self._ground_points_camera: Optional[np.ndarray] = None
        self._ground_points_projector: Optional[np.ndarray] = None
        self._reprojection_error: float = 0.0
        self._object_points: Optional[np.ndarray] = None
        self._image_points: Optional[np.ndarray] = None
        self._target_status: List[str] = []
        self._target_info: List[Dict[str, Any]] = []
        self._animation_start_times: Dict[int, float] = {}
        self._token_names: Dict[int, str] = {}
        self._current_time: float = 0.0
        self._cached_canvas: Optional[np.ndarray] = None
        self._last_render_params: Dict[str, Any] = {}
        self.is_dynamic = True

    def on_enter(self, payload: Any = None) -> None:
        self._stage = "PLACEMENT"
        self.increment_version()
        self._ppi = self.context.map_config_manager.get_ppi()
        self._reprojection_error = 0.0
        self._object_points = None
        self._image_points = None
        self._current_time = 0.0
        self._known_targets = {}
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        # Load ground points (Z=0) from projector calibration
        try:
            if os.path.exists("projector_calibration.npz"):
                data = np.load("projector_calibration.npz")
                self._ground_points_camera = data["camera_points"]
                self._ground_points_projector = data["projector_points"]
                logging.info(
                    "Loaded %d ground points from projector calibration.",
                    len(self._ground_points_camera),
                )
        except Exception as e:
            logging.error("Failed to load projector calibration points: %s", e)
            self._ground_points_camera = None
            self._ground_points_projector = None

        # Load token heights, names, and sizes from global config
        self._token_heights = {}
        self._token_names = {}
        self._token_sizes = {}
        for (
            aid,
            defn,
        ) in (
            self.context.map_config_manager.data.global_settings.aruco_defaults.items()
        ):
            resolved = self.context.map_config_manager.resolve_token_profile(aid)
            self._token_heights[aid] = resolved.height_mm
            self._token_names[aid] = resolved.name
            self._token_sizes[aid] = resolved.size

        # Define 5 Target Zones (in projector pixels)
        # Shifted slightly to break symmetry and avoid ambiguities
        w, h = self.context.app_config.width, self.context.app_config.height
        margin_x = 220
        margin_y = 180
        self._target_zones = [
            (margin_x, margin_y, 10),  # TL (Slightly shifted)
            (w - margin_x + 30, margin_y - 20, 11),  # TR (Asymmetric shift)
            (margin_x - 40, h - margin_y + 15, 12),  # BL (Asymmetric shift)
            (w - margin_x - 15, h - margin_y - 35, 13),  # BR (Asymmetric shift)
            (w // 2 + 25, h // 2 - 10, 14),  # C (Slightly off-center)
        ]
        self._target_status = ["IDLE"] * len(self._target_zones)
        self._target_info = [{} for _ in range(len(self._target_zones))]
        self._animation_start_times = {}
        self.context.notifications.add_notification("Place tokens on target zones.")

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def _on_retry_triggered(self):
        """Callback for when the retry gesture hold is completed."""
        self.context.notifications.add_notification("Calibration discarded.")
        self._stage = "PLACEMENT"
        self.increment_version()

    def _on_start_capture_triggered(self):
        """Callback for when the capture gesture hold is completed."""
        self._stage = "CAPTURE"
        self.increment_version()

    def _on_accept_triggered(self):
        """Callback for when the accept gesture hold is completed."""
        if self._rotation_vector is not None and self._translation_vector is not None:
            storage = self.context.app_config.storage_manager
            output_file = (
                storage.get_data_path("camera_extrinsics.npz")
                if storage
                else "camera_extrinsics.npz"
            )
            save_camera_extrinsics(
                self._rotation_vector,
                self._translation_vector,
                output_file=output_file,
            )
            self.context.notifications.add_notification("Extrinsics saved.")
        self._stage = "DONE"  # Mark as finished for update loop

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        self._current_time = current_time
        if self._stage == "PLACEMENT":
            # Continuous detection using context-provided results
            raw = self.context.raw_aruco
            if raw and raw.get("ids") is not None:
                corners = raw.get("corners", [])
                ids = raw.get("ids", [])

                # Reset status, detected IDs, and known targets for this frame
                self._target_status = ["IDLE"] * len(self._target_zones)
                self._target_info = [{} for _ in range(len(self._target_zones))]
                self._detected_ids = {}
                self._known_targets = {}

                for i, marker_id_raw in enumerate(ids):
                    # Ensure marker_id is an integer (flatten if it's a list/array from raw detection)
                    if isinstance(marker_id_raw, (list, np.ndarray)):
                        aid = int(marker_id_raw[0])
                    else:
                        aid = int(marker_id_raw)

                    marker_corners = corners[i]
                    c_cam = np.mean(marker_corners, axis=0)

                    # Project to projector space for target matching (Z=0 assumption for matching)
                    pts_cam = np.array([c_cam], dtype=np.float32).reshape(-1, 1, 2)
                    pts_proj = cv2.perspectiveTransform(
                        pts_cam, self.context.app_config.projector_matrix
                    ).reshape(-1, 2)
                    px, py = pts_proj[0]

                    # 1. Match by ID (preferred if suggested IDs are used)
                    best_idx = -1
                    for idx, (_, _, sid) in enumerate(self._target_zones):
                        if aid == sid:
                            best_idx = idx
                            break

                    # 2. Match by proximity if ID matching failed
                    if best_idx == -1:
                        best_dist = 150.0  # Threshold in projector pixels
                        for idx, (tx, ty, _) in enumerate(self._target_zones):
                            dist = math.sqrt((px - tx) ** 2 + (py - ty) ** 2)
                            if dist < best_dist:
                                best_dist = dist
                                best_idx = idx

                    if best_idx != -1:
                        info = {"aid": aid}
                        if aid in self._token_heights:
                            self._target_status[best_idx] = "VALID"
                            info["height"] = self._token_heights[aid]
                            info["size"] = self._token_sizes.get(aid, 1)
                            info["name"] = self._token_names.get(aid, f"Token {aid}")
                            # Trigger animation if it's the first time it becomes valid
                            if best_idx not in self._animation_start_times:
                                self._animation_start_times[best_idx] = current_time
                            # Capture coordinates for solvePnP
                            tx, ty, _ = self._target_zones[best_idx]
                            self._detected_ids[aid] = (c_cam[0], c_cam[1])
                            self._known_targets[aid] = (float(tx), float(ty))
                        else:
                            self._target_status[best_idx] = "UNKNOWN"
                            if best_idx in self._animation_start_times:
                                del self._animation_start_times[best_idx]
                        self._target_info[best_idx] = info

                # Clean up animation timers for IDLE targets
                for idx in range(len(self._target_status)):
                    if (
                        self._target_status[idx] == "IDLE"
                        and idx in self._animation_start_times
                    ):
                        del self._animation_start_times[idx]

            # Validation: At least 3 targets are "VALID"
            valid_count = self._target_status.count("VALID")

            # Use Fist or Victory (hold) to trigger capture if enough tokens
            if valid_count >= 3 and inputs:
                gesture = inputs[0].gesture
                if gesture == GestureType.CLOSED_FIST:
                    self._stage = "CAPTURE"
                elif gesture == GestureType.VICTORY:
                    if not self.context.events.has_event(TimerKey.CALIBRATION_STAGE):
                        self.context.events.schedule(
                            1.0,
                            self._on_start_capture_triggered,
                            key=TimerKey.CALIBRATION_STAGE,
                        )
                else:
                    self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
            else:
                self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        elif self._stage == "CAPTURE":
            # Clear any pending timers from PLACEMENT
            self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
            # Run solvePnP
            if self.context.app_config.camera_matrix is None:
                self.context.notifications.add_notification(
                    "Error: Camera intrinsics missing."
                )
                self._stage = "ERROR"
                return None

            raw = self.context.raw_aruco
            formatted_corners = None
            formatted_ids = None
            if raw and raw.get("ids") is not None:
                corners = raw.get("corners", [])
                ids = raw.get("ids", [])
                formatted_corners = tuple(np.array(c).reshape(1, 4, 2) for c in corners)
                formatted_ids = np.array(ids)

            # CRITICAL: Pass known_targets so calibrate_extrinsics uses (tx, ty, h)
            # instead of estimating (X, Y) from a potentially parallax-distorted homography.
            result = calibrate_extrinsics(
                None,
                self.context.app_config.projector_matrix,
                self.context.app_config.camera_matrix,
                self.context.app_config.distortion_coefficients,
                self._token_heights,
                self._ppi,
                ground_points_camera=self._ground_points_camera,
                ground_points_projector=self._ground_points_projector,
                known_targets=self._known_targets,
                aruco_corners=formatted_corners,
                aruco_ids=formatted_ids,
            )

            if result:
                (
                    self._rotation_vector,
                    self._translation_vector,
                    self._object_points,
                    self._image_points,
                ) = result

                # Calculate Reprojection Error
                projected_points, _ = cv2.projectPoints(
                    self._object_points,
                    self._rotation_vector,
                    self._translation_vector,
                    self.context.app_config.camera_matrix,
                    self.context.app_config.distortion_coefficients,
                )
                projected_points = projected_points.reshape(-1, 2)

                errors = np.linalg.norm(self._image_points - projected_points, axis=1)
                self._reprojection_error = np.sqrt(np.mean(errors**2))

                self.context.notifications.add_notification(
                    f"Calibration Error: {self._reprojection_error:.2f} px"
                )
                self._stage = "VALIDATION"
            else:
                self.context.notifications.add_notification("Calibration failed.")
                self._stage = "PLACEMENT"

        elif self._stage == "VALIDATION":
            if inputs:
                gesture = inputs[0].gesture
                # Accept (Hold Victory)
                if gesture == GestureType.VICTORY:
                    if not self.context.events.has_event(TimerKey.CALIBRATION_STAGE):
                        self.context.events.schedule(
                            1.0, self._on_accept_triggered, key=TimerKey.CALIBRATION_STAGE
                        )
                # Retry (Hold Fist)
                elif gesture == GestureType.CLOSED_FIST:
                    if not self.context.events.has_event(TimerKey.CALIBRATION_STAGE):
                        self.context.events.schedule(
                            2.0, self._on_retry_triggered, key=TimerKey.CALIBRATION_STAGE
                        )
                else:
                    self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
            else:
                self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        elif self._stage == "DONE":
            return SceneTransition(SceneId.MENU)

        return None

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Calibration scenes only need standard scene + UI layers."""
        return self.get_scene_with_ui_stack(app)

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        current_time = self._current_time
        ppi = self._ppi if self._ppi > 0 else 96.0

        # Rendering Parameters for Cache Matching
        render_params = {
            "stage": self._stage,
            "target_status": self._target_status.copy(),
            "target_info": self._target_info.copy(),
            "has_reprojection": self._object_points is not None,
            "ppi": ppi,
        }

        # Check for cache hit
        # Note: We ignore animations (expanding circles) for the base cache to avoid
        # 60fps cache misses. Animations are drawn on top.
        if (
            self._cached_canvas is not None
            and self._cached_canvas.shape[:2] == (h, w)
            and render_params == self._last_render_params
        ):
            canvas = self._cached_canvas.copy()
        else:
            # Cache Miss: Redraw everything
            canvas = np.full((h, w, 3), 200, dtype=np.uint8)  # Light gray "Arena"

            # Draw Target Zones
            for idx, (tx, ty, tid) in enumerate(self._target_zones):
                status = self._target_status[idx]
                info = self._target_info[idx]

                # Default size is 1x1 inch
                token_size = info.get("size", 1)
                rect_size = int(token_size * ppi)
                half_size = rect_size // 2

                # Default IDLE: White rectangle
                color = (255, 255, 255)
                thickness = 2
                label = "Target"

                if status == "VALID":
                    color = (0, 255, 0)  # Green
                    thickness = -1  # Filled
                    label = info.get("name", "Locked")

                    # Metadata
                    height = info.get("height", 0.0)
                    draw_text_with_background(
                        canvas,
                        f"{label}: {height}mm",
                        (tx - half_size, ty - half_size - 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 100, 0),
                        1,
                    )

                elif status == "UNKNOWN":
                    color = (150, 150, 150)  # Gray
                    aid = info.get("aid", "???")
                    label = f"Unknown ID {aid}"
                    thickness = 1

                # Draw the main target rectangle
                cv2.rectangle(
                    canvas,
                    (tx - half_size, ty - half_size),
                    (tx + half_size, ty + half_size),
                    color,
                    thickness,
                )

                # Label below
                draw_text_with_background(
                    canvas,
                    label,
                    (tx - half_size, ty + half_size + 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color if thickness > 0 else (0, 100, 0),
                    1 if thickness > 0 else 2,
                )

            # Verification Overlay: Visual Feedback
            if (
                self._stage == "VALIDATION"
                and self._rotation_vector is not None
                and self._translation_vector is not None
                and self._object_points is not None
            ):
                # Calculate reprojected points (Camera Space)
                projected_points, _ = cv2.projectPoints(
                    self._object_points,
                    self._rotation_vector,
                    self._translation_vector,
                    self.context.app_config.camera_matrix,
                    self.context.app_config.distortion_coefficients,
                )
                projected_points = projected_points.reshape(-1, 2)

                # Transform both sets to Projector Space for rendering
                image_pts_reshaped = self._image_points.reshape(-1, 1, 2)
                detected_proj = cv2.perspectiveTransform(
                    image_pts_reshaped, self.context.app_config.projector_matrix
                ).reshape(-1, 2)

                reprojected_proj = cv2.perspectiveTransform(
                    projected_points.reshape(-1, 1, 2),
                    self.context.app_config.projector_matrix,
                ).reshape(-1, 2)

                # Draw residuals
                for i in range(len(detected_proj)):
                    p_det = detected_proj[i]
                    p_rep = reprojected_proj[i]
                    error_px = np.linalg.norm(
                        self._image_points[i] - projected_points[i]
                    )
                    color = (
                        (0, 255, 0)
                        if error_px < 2.0
                        else (0, 255, 255)
                        if error_px < 5.0
                        else (0, 0, 255)
                    )
                    pt1, pt2 = (
                        (int(p_det[0]), int(p_det[1])),
                        (
                            int(p_rep[0]),
                            int(p_rep[1]),
                        ),
                    )
                    cv2.line(canvas, pt1, pt2, color, 2)
                    cv2.line(
                        canvas,
                        (pt1[0] - 5, pt1[1]),
                        (pt1[0] + 5, pt1[1]),
                        (0, 255, 0),
                        2,
                    )
                    cv2.line(
                        canvas,
                        (pt1[0], pt1[1] - 5),
                        (pt1[0], pt1[1] + 5),
                        (0, 255, 0),
                        2,
                    )
                    cv2.circle(canvas, pt2, 5, (0, 0, 255), 2)

                # HUD
                rms = self._reprojection_error
                status_color = (
                    (0, 255, 0)
                    if rms < 2.0
                    else (0, 255, 255)
                    if rms < 5.0
                    else (0, 0, 255)
                )
                status_text = "GOOD" if rms < 2.0 else "FAIR" if rms < 5.0 else "POOR"
                draw_text_with_background(
                    canvas,
                    f"Error: {rms:.2f} px ({status_text})",
                    (w // 2 - 130, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    status_color,
                    2,
                    bg_color=(50, 50, 50),
                )

            # Update cache
            self._cached_canvas = canvas.copy()
            self._last_render_params = render_params

        # Draw Animations on top of (potentially cached) canvas
        for idx, (tx, ty, tid) in enumerate(self._target_zones):
            if (
                self._target_status[idx] == "VALID"
                and idx in self._animation_start_times
            ):
                elapsed = current_time - self._animation_start_times[idx]
                if elapsed < 0.5:
                    growth = int(20 * (1.0 - elapsed / 0.5))
                    token_size = self._target_info[idx].get("size", 1)
                    rect_size = int(token_size * ppi)
                    half_size = rect_size // 2
                    cv2.rectangle(
                        canvas,
                        (tx - half_size - growth, ty - half_size - growth),
                        (tx + half_size + growth, ty + half_size + growth),
                        (0, 255, 0),
                        2,
                    )

        # Instructions (always on top)
        instr = ""
        if self._stage == "PLACEMENT":
            instr = "Victory (hold) or Fist to calibrate (Need 3+ tokens)"
        elif self._stage == "VALIDATION":
            instr = "Victory (hold) to Accept, Fist (hold 2s) to Retry"
        draw_text_with_background(
            canvas, instr, (50, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2
        )

        return canvas


class PpiCalibrationScene(Scene):
    """Handles PPI calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "DETECTING"  # DETECTING | CONFIRMING
        self._candidate_ppi = 0.0
        self.is_dynamic = True

    def on_enter(self, payload: Any = None) -> None:
        self._stage = "DETECTING"
        self._candidate_ppi = 0.0
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == "CONFIRMING" and inputs:
            gesture = inputs[0].gesture
            if gesture == GestureType.VICTORY:
                self.context.map_config_manager.set_ppi(self._candidate_ppi)
                # Update the active config so layers (like HandMaskLayer) can use it immediately
                self.context.app_config.projector_ppi = self._candidate_ppi

                # Refresh current map's base scale if loaded
                map_system = self.context.map_system
                if map_system.is_map_loaded():
                    filename = map_system.svg_loader.filename
                    entry = self.context.map_config_manager.data.maps.get(filename)
                    if entry and entry.grid_spacing_svg > 0:
                        map_system.base_scale = (
                            entry.physical_unit_inches * self._candidate_ppi
                        ) / entry.grid_spacing_svg
                        logging.info(
                            f"Updated base scale for {os.path.basename(filename)} to {map_system.base_scale:.4f}"
                        )

                self.context.notifications.add_notification(
                    f"PPI saved: {self._candidate_ppi:.2f}"
                )
                return SceneTransition(SceneId.MENU)
            elif gesture == GestureType.OPEN_PALM:
                self._stage = "DETECTING"
        return None

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Calibration scenes only need standard scene + UI layers."""
        return self.get_scene_with_ui_stack(app)

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        canvas = np.full(
            (h, w, 3), 0, dtype=np.uint8
        )  # Black background to avoid glare

        cx, cy = w // 2, h // 2

        # Text instructions
        cv2.putText(
            canvas,
            "Place physical PPI target (100mm) on table.",
            (cx - 280, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )

        cv2.putText(
            canvas,
            "Target contains markers ID 0 and 1.",
            (cx - 200, cy + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
        )

        if self._stage == "DETECTING":
            raw = self.context.raw_aruco
            corners = []
            ids = []

            if raw and raw.get("ids") is not None and len(raw.get("ids", [])) >= 2:
                ids = raw.get("ids", [])
                corners = raw.get("corners", [])

            # Ensure ids are flat integers for robust check
            flat_ids = []
            for item in ids:
                if isinstance(item, (list, np.ndarray)):
                    flat_ids.append(int(item[0]))
                else:
                    flat_ids.append(int(item))

            # Fallback to direct detection from frame if worker is slow/missing
            if (
                0 not in flat_ids or 1 not in flat_ids
            ) and self.context.last_camera_frame is not None:
                ppi = calculate_ppi_from_frame(
                    self.context.last_camera_frame,
                    self.context.app_config.projector_matrix,
                    target_dist_mm=100.0,
                )
            elif 0 in flat_ids and 1 in flat_ids:
                # Re-format corners to (1, 4, 2) as expected by calculate_ppi_from_frame
                formatted_corners = tuple(np.array(c).reshape(1, 4, 2) for c in corners)
                formatted_ids = np.array(flat_ids)

                ppi = calculate_ppi_from_frame(
                    None,
                    self.context.app_config.projector_matrix,
                    target_dist_mm=100.0,
                    aruco_corners=formatted_corners,
                    aruco_ids=formatted_ids,
                )
            else:
                ppi = None

            if ppi:
                self._candidate_ppi = ppi
                self._stage = "CONFIRMING"
                self.context.notifications.add_notification(
                    f"Detected PPI: {ppi:.2f}. Victory to save."
                )

        elif self._stage == "CONFIRMING":
            cv2.putText(
                canvas,
                f"Detected PPI: {self._candidate_ppi:.2f}",
                (cx - 150, cy - 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                canvas,
                "VICTORY to save, PALM to retry",
                (cx - 200, cy + 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )

        return canvas


class GridOverlay:
    """Manages the state of the calibration grid overlay."""

    def __init__(self, start_spacing: float, config: AppConfig):
        self.spacing = start_spacing
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.config = config

    @property
    def width(self) -> int:
        return self.config.width

    @property
    def height(self) -> int:
        return self.config.height

    def pan(self, dx: float, dy: float) -> None:
        self.offset_x += dx
        self.offset_y += dy

    def zoom_pinned(self, factor: float, center_point: Tuple[int, int]) -> None:
        # Ignore gesture center, always pivot around the grid origin (offset_x, offset_y)
        # This keeps the "anchor" stationary while scaling the grid.
        self.spacing *= factor


class MapGridCalibrationScene(Scene):
    """Handles map grid calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.interaction_controller = MapInteractionController()
        self.is_interacting = False
        self.calib_map_grid_size_inches = 1.0
        self.grid_overlay: Optional[GridOverlay] = None
        self.is_dynamic = True
        self._save_triggered = False

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False
        self._save_triggered = False
        self.increment_version()
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        # Check for existing calibration
        filename = map_system.svg_loader.filename if map_system.svg_loader else None
        entry = (
            map_config.data.maps.get(os.path.abspath(filename)) if filename else None
        )

        if entry and entry.grid_spacing_svg > 0:
            # Initialize from existing config
            start_spacing = entry.grid_spacing_svg * map_system.state.zoom
            self.grid_overlay = GridOverlay(
                start_spacing,
                self.context.app_config,
            )
            # Use world_to_screen to find the current screen position of the saved world origin
            sx, sy = map_system.world_to_screen(
                entry.grid_origin_svg_x, entry.grid_origin_svg_y
            )
            self.grid_overlay.offset_x = sx
            self.grid_overlay.offset_y = sy
            logging.info(
                "Restored grid for %s: spacing=%.1f, offset=(%.1f, %.1f)",
                filename,
                start_spacing,
                sx,
                sy,
            )
        else:
            # Fallback/Default behavior
            ppi = map_config.get_ppi()
            if ppi <= 0:
                ppi = 96.0

            start_spacing = ppi * self.calib_map_grid_size_inches
            self.grid_overlay = GridOverlay(
                start_spacing,
                self.context.app_config,
            )

            # Center the grid initially
            self.grid_overlay.offset_x = self.context.app_config.width / 2
            self.grid_overlay.offset_y = self.context.app_config.height / 2
            logging.info("Initialized default grid (centered)")

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def _on_save_triggered(self):
        """Callback for when the save gesture hold is completed."""
        self._save_calibration()
        self._save_triggered = True

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._save_triggered:
            return SceneTransition(SceneId.MENU)

        primary_gesture = inputs[0].gesture if inputs else GestureType.NONE

        # Confirm gesture
        if primary_gesture == GestureType.VICTORY:
            if not self.context.events.has_event(TimerKey.CALIBRATION_STAGE):
                self.context.events.schedule(
                    1.0, self._on_save_triggered, key=TimerKey.CALIBRATION_STAGE
                )
        else:
            self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        # Process grid interactions
        if self.grid_overlay:
            self.is_interacting = self.interaction_controller.process_gestures(
                inputs, self.grid_overlay
            )

        return None

    def _save_calibration(self):
        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        if not map_system.svg_loader:
            self.context.notifications.add_notification(
                "Error: No map loaded for calibration."
            )
            return

        filename = map_system.svg_loader.filename

        if not self.grid_overlay:
            return

        # Calculate SVG parameters from overlay state
        # Spacing:
        # Overlay pixels = spacing_px
        # Map Zoom = map_pixels / svg_units
        # svg_spacing = spacing_px / map_zoom

        # NOTE: This assumes uniform scale and no rotation affecting the spacing ratio significantly
        # (rotation is fine, but non-uniform scaling/skew would be complex). MapSystem is uniform.
        derived_spacing_svg = self.grid_overlay.spacing / map_system.state.zoom

        # Origin:
        # The grid origin is at screen (offset_x, offset_y).
        # We want the world coordinate corresponding to this screen pixel.
        wx, wy = map_system.screen_to_world(
            self.grid_overlay.offset_x, self.grid_overlay.offset_y
        )

        logging.info(
            "Calibrated %s: Spacing=%.1f, Origin=(%.1f, %.1f)",
            filename,
            derived_spacing_svg,
            wx,
            wy,
        )

        map_config.save_map_grid_config(
            filename,
            grid_spacing_svg=derived_spacing_svg,
            grid_origin_svg_x=wx,
            grid_origin_svg_y=wy,
            physical_unit_inches=self.calib_map_grid_size_inches,
            scale_factor_1to1=map_system.base_scale,  # Preserve existing base scale or update?
            # Design doc says: "Updates the map configuration with the new grid parameters."
            # The base scale itself (calibration of 1:1) is distinct from the GRID alignment.
            # Usually scale_factor_1to1 is derived from PPI and grid spacing.
            # If we change grid spacing, we might imply a new 1:1 scale if the physical size is fixed.
            # But here we are finding the grid within the map.
            # The base scale is "how much zoom to match 1 SVG unit to 1 inch?"
            # No, base_scale is "scale factor to match 1 GRID UNIT to N INCHES".
            # S_1:1 = (Physical * PPI) / SVG_Spacing.
            # So if we change SVG_Spacing, we effectively change S_1:1.
        )

        # Recalculate base scale based on new grid spacing
        # S_1:1 = (Physical * PPI) / Spacing_SVG
        ppi = map_config.get_ppi()
        if ppi > 0:
            new_base_scale = (
                self.calib_map_grid_size_inches * ppi
            ) / derived_spacing_svg
            # Update the config with this new base scale
            # Wait, save_map_grid_config takes scale_factor_1to1 as arg.
            # I should calculate it and pass it.
            map_config.save_map_grid_config(
                filename,
                grid_spacing_svg=derived_spacing_svg,
                grid_origin_svg_x=wx,
                grid_origin_svg_y=wy,
                physical_unit_inches=self.calib_map_grid_size_inches,
                scale_factor_1to1=new_base_scale,
            )
            # Update system immediately
            map_system.base_scale = new_base_scale

        self.context.notifications.add_notification("Map grid calibrated.")

    @property
    def blocking(self) -> bool:
        """Map grid calibration needs to show the map behind the grid crosses."""
        return False

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Map grid calibration needs map + scene + UI layers."""
        return [app.map_layer] + self.get_scene_with_ui_stack(app)

    def render(self, frame: np.ndarray) -> np.ndarray:
        # The main app loop renders the map background.
        # Here we render the grid overlay using small crosses at intersections.

        if not self.grid_overlay:
            return frame

        # Overlay parameters
        spacing = self.grid_overlay.spacing
        off_x = self.grid_overlay.offset_x
        off_y = self.grid_overlay.offset_y
        w, h = self.grid_overlay.width, self.grid_overlay.height

        if spacing <= 0:
            return frame

        color_green = (0, 255, 0)
        color_black = (0, 0, 0)
        cross_size = 10  # Length of each arm in pixels

        # Calculate range of intersection indices
        start_i = int(math.ceil(-off_x / spacing))
        end_i = int(math.floor((w - 1 - off_x) / spacing))
        start_j = int(math.ceil(-off_y / spacing))
        end_j = int(math.floor((h - 1 - off_y) / spacing))

        for i in range(start_i, end_i + 1):
            x = int(round(off_x + i * spacing))
            for j in range(start_j, end_j + 1):
                y = int(round(off_y + j * spacing))

                # Draw cross with outline
                # Horizontal segments
                cv2.line(
                    frame, (x - cross_size, y), (x + cross_size, y), color_black, 3
                )
                cv2.line(
                    frame, (x - cross_size, y), (x + cross_size, y), color_green, 1
                )

                # Vertical segments
                cv2.line(
                    frame, (x, y - cross_size), (x, y + cross_size), color_black, 3
                )
                cv2.line(
                    frame, (x, y - cross_size), (x, y + cross_size), color_green, 1
                )

        # Highlight Origin specifically
        ox, oy = int(round(off_x)), int(round(off_y))
        if 0 <= ox < w and 0 <= oy < h:
            cv2.circle(frame, (ox, oy), 8, color_black, -1)
            cv2.circle(frame, (ox, oy), 5, (0, 255, 0), -1)

        return frame


class Projector3DCalibStage(Enum):
    START = auto()
    PLACE_BOX = auto()
    CAPTURING = auto()
    CALIBRATING = auto()
    DONE = auto()


class Projector3DCalibrationScene(Scene):
    """Handles 3D Projector Pose Calibration using a physical box target."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.is_dynamic = True
        self.stage = Projector3DCalibStage.START
        self.correspondences = []
        self.current_box_pos_idx = 0
        self.max_box_positions = 5
        self._cooldown = 2.0
        self._can_gesture = True
        self._transition_to_menu = False

        from light_map.projector_3d_layer import (
            Projector3DPatternLayer,
            Projector3DFeedbackLayer,
        )

        self.pattern_layer = Projector3DPatternLayer(
            context.state, context.app_config.width, context.app_config.height
        )
        self.feedback_layer = Projector3DFeedbackLayer(
            context.state, context.app_config.width, context.app_config.height
        )

    def on_enter(self, payload: dict | None = None) -> None:
        logging.info("Projector3DCalibrationScene: Scene started.")
        self.stage = Projector3DCalibStage.START
        self.correspondences = []
        self.current_box_pos_idx = 0
        self._can_gesture = True
        self._transition_to_menu = False
        self._update_layer_markers()
        self.increment_version()
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def _on_cooldown_expired(self):
        self._can_gesture = True

    def _on_done_delay_expired(self):
        self._transition_to_menu = True

    @property
    def blocking(self) -> bool:
        return True

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        return [
            self.pattern_layer,
            self.feedback_layer,
            app.notification_layer,
            app.cursor_layer,
        ]

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        if self._transition_to_menu:
            return SceneTransition(SceneId.MENU)

        old_stage = self.stage

        # Continuously update detected IDs for feedback
        raw = self.context.raw_aruco
        if raw and raw.get("ids") is not None:
            # ids can be a list or a numpy array of arrays
            ids = raw.get("ids", [])
            detected = []
            for item in ids:
                if isinstance(item, (list, np.ndarray)):
                    detected.append(int(item[0]))
                else:
                    detected.append(int(item))
            self.feedback_layer.detected_ids = set(detected)
        else:
            self.feedback_layer.detected_ids = set()

        if self.stage == Projector3DCalibStage.START:
            self.stage = Projector3DCalibStage.PLACE_BOX
            self._update_layer_markers()

        elif self.stage == Projector3DCalibStage.PLACE_BOX:
            # Alternate gestures to prevent double-triggering
            expected_gesture = (
                GestureType.VICTORY
                if self.current_box_pos_idx % 2 == 0
                else GestureType.SHAKA
            )

            for inp in inputs:
                if inp.gesture == expected_gesture and self._can_gesture:
                    self._can_gesture = False
                    self.context.events.schedule(
                        self._cooldown,
                        self._on_cooldown_expired,
                        key=TimerKey.CALIBRATION_STAGE,
                    )
                    self.stage = Projector3DCalibStage.CAPTURING
                    return None

        elif self.stage == Projector3DCalibStage.CAPTURING:
            # In the next frame, we'll process the data
            # This allows the render() call to show a "Capturing..." message if needed
            self._do_capture()
            if self.current_box_pos_idx >= self.max_box_positions:
                self.stage = Projector3DCalibStage.CALIBRATING
            else:
                self.stage = Projector3DCalibStage.PLACE_BOX
            self._update_layer_markers()

        elif self.stage == Projector3DCalibStage.CALIBRATING:
            self._run_calibration()
            self.stage = Projector3DCalibStage.DONE
            self.context.events.schedule(
                3.0, self._on_done_delay_expired, key=TimerKey.CALIBRATION_STAGE
            )

        if self.stage != old_stage:
            logging.info("Projector3DCalibrationScene: Stage changed to %s", self.stage)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        # Rendering is handled by the layer stack in get_active_layers
        return frame

    def _update_layer_markers(self):
        """Generates markers and box outline to display based on current stage."""
        w, h = self.context.app_config.width, self.context.app_config.height
        ppi = getattr(self.context.app_config, "projector_ppi", 96.0)

        # 1. Define Box Position and Outline
        # Physical box: 295mm (length) x 188mm (width)
        # Orient horizontally: longest side along Screen X (width)
        bl_mm = self.context.app_config.calibration_box_length_mm  # 295
        bw_mm = self.context.app_config.calibration_box_width_mm  # 188

        # Approximate pixels using PPI
        # Now length is Screen X, width is Screen Y
        bl_px = int((bl_mm / 25.4) * ppi)
        bw_px = int((bw_mm / 25.4) * ppi)

        # Structured Positions: Center-Top, Center-Bottom, TL, TR, BL, BR
        # Coordinates for the center of the box
        pos_list = [
            (w // 2, h // 4),  # Center-Top
            (w // 2, 3 * h // 4),  # Center-Bottom
            (w // 4, h // 4),  # Top-Left
            (3 * w // 4, h // 4),  # Top-Right
            (w // 4, 3 * h // 4),  # Bottom-Left
            (3 * w // 4, 3 * h // 4),  # Bottom-Right
        ]
        self.max_box_positions = len(pos_list)  # Update max steps to 6

        s_idx = self.current_box_pos_idx % len(pos_list)
        center_x, center_y = pos_list[s_idx]

        # Clamp center to keep box on screen with 20px margin
        center_x = max(bl_px // 2 + 20, min(w - bl_px // 2 - 20, center_x))
        center_y = max(bw_px // 2 + 20, min(h - bw_px // 2 - 20, center_y))

        # Box corners for outline (Longest side horizontal)
        box_rect = np.array(
            [
                [center_x - bl_px // 2, center_y - bw_px // 2],
                [center_x + bl_px // 2, center_y - bw_px // 2],
                [center_x + bl_px // 2, center_y + bw_px // 2],
                [center_x - bl_px // 2, center_y + bw_px // 2],
            ]
        )

        # 2. Define 6 markers for the box top (3x2 grid)
        box_ids = [10, 11, 12, 13, 14, 15]
        box_markers = []

        # Use a safe margin inside the box
        margin = 40
        msize = 100

        # Markers distributed along the long horizontal side (3 columns)
        # and short vertical side (2 rows)
        if bl_px > (msize * 3 + margin * 2):
            col_xs = np.linspace(
                center_x - bl_px // 2 + margin + msize // 2,
                center_x + bl_px // 2 - margin - msize // 2,
                3,
            )
        else:
            col_xs = [center_x] * 3

        if bw_px > (msize * 2 + margin * 2):
            row_ys = np.linspace(
                center_y - bw_px // 2 + margin + msize // 2,
                center_y + bw_px // 2 - margin - msize // 2,
                2,
            )
        else:
            row_ys = [center_y] * 2

        for i, mx in enumerate(col_xs):
            for j, my in enumerate(row_ys):
                # Correct indexing for 3 columns x 2 rows
                marker_idx = i + j * 3
                if marker_idx >= len(box_ids):
                    continue

                corners = np.array(
                    [
                        [mx - msize // 2, my - msize // 2],
                        [mx + msize // 2, my - msize // 2],
                        [mx + msize // 2, my + msize // 2],
                        [mx - msize // 2, my + msize // 2],
                    ]
                )
                box_markers.append((box_ids[marker_idx], corners))

        # 3. Define 4 reference markers for the table (Corners)
        # We'll place them at the corners but hide if they overlap with the box
        tsize = 120  # Increased from 100

        # Determine instruction position: if box is in top half, move instructions to bottom
        if center_y < h // 2:
            self.feedback_layer.instruction_pos = (100, h - 100)
            # Top markers can be at 50 if instructions moved to bottom
            raw_table_markers = [
                (20, 50, 50),
                (21, w - 50 - tsize, 50),
                (22, 50, h - 250),  # BL (Offset for instructions at bottom)
                (23, w - 50 - tsize, h - 250),  # BR
            ]
        else:
            self.feedback_layer.instruction_pos = (100, 100)
            raw_table_markers = [
                (20, 50, 200),  # TL (Offset for instructions at top)
                (21, w - 50 - tsize, 200),  # TR
                (22, 50, h - 50 - tsize),  # BL
                (23, w - 50 - tsize, h - 50 - tsize),  # BR
            ]

        table_markers = []
        for tid, tx, ty in raw_table_markers:
            # Check if this reference marker overlaps with the box outline
            # A simple bounding box check
            m_rect = [tx, ty, tx + tsize, ty + tsize]
            b_rect = [
                center_x - bw_px // 2,
                center_y - bl_px // 2,
                center_x + bw_px // 2,
                center_y + bl_px // 2,
            ]

            # If no overlap, add it
            if (
                m_rect[0] > b_rect[2]
                or m_rect[2] < b_rect[0]
                or m_rect[1] > b_rect[3]
                or m_rect[3] < b_rect[1]
            ):
                corners = np.array(
                    [
                        [tx, ty],
                        [tx + tsize, ty],
                        [tx + tsize, ty + tsize],
                        [tx, ty + tsize],
                    ]
                )
                table_markers.append((tid, corners))
            else:
                logging.debug("Hiding reference marker %d due to box overlap", tid)

        self.pattern_layer.box_markers = box_markers
        self.pattern_layer.table_markers = table_markers
        self.pattern_layer.box_outline = box_rect
        self.pattern_layer.increment_version()

        self.feedback_layer.box_markers = box_markers
        self.feedback_layer.table_markers = table_markers

        expected_gesture_name = (
            "Victory" if self.current_box_pos_idx % 2 == 0 else "Shaka"
        )
        self.feedback_layer.instructions = (
            f"Step {self.current_box_pos_idx + 1}/{self.max_box_positions}: "
            f"Place box (H={self.context.app_config.calibration_box_height_mm}mm) "
            f"and show {expected_gesture_name} gesture."
        )
        logging.info(
            "Projector3DCalibrationScene: Instructions: %s",
            self.feedback_layer.instructions,
        )

    def _do_capture(self):
        """Captures the current frame and reconstructs 3D points."""
        logging.info("Projector3DCalibrationScene: Capturing 3D Projector Points...")

        raw = self.context.raw_aruco
        if not raw or raw.get("ids") is None:
            logging.warning(
                "Projector3DCalibrationScene: No ArUco markers detected for capture!"
            )
            self.context.notifications.add_notification("No markers detected!")
            return

        ids = raw.get("ids")
        corners_camera = raw.get("corners")

        # Load camera calibration for back-projection from AppContext
        camera_matrix = self.context.app_config.camera_matrix
        distortion_coefficients = self.context.app_config.distortion_coefficients
        rotation_vector_camera = self.context.app_config.rotation_vector
        translation_vector_camera = self.context.app_config.translation_vector

        if camera_matrix is None or rotation_vector_camera is None:
            logging.error(
                "Projector3DCalibrationScene: Camera calibration missing in AppContext!"
            )
            self.context.notifications.add_notification(
                "Error: Camera extrinsics missing. Run Step 4 first."
            )
            # We don't have an ERROR stage in this scene, but we can go back to PLACE_BOX
            # or just return. Returning to PLACE_BOX is safer.
            return

        rotation_matrix_camera, _ = cv2.Rodrigues(rotation_vector_camera)
        # Camera position in world coordinates: C = -R^T * t
        # We flatten to ensure it's a (3,) vector, avoiding broadcasting issues in world_point calculation
        camera_center_world = (
            -rotation_matrix_camera.T @ translation_vector_camera
        ).flatten()

        # Collect all expected marker info from the layers
        marker_map = {}  # id -> (corners_projector, height, is_box)
        for aid, c_p in self.pattern_layer.box_markers:
            marker_map[aid] = (
                c_p,
                self.context.app_config.calibration_box_height_mm,
                True,
            )
        for aid, c_p in self.pattern_layer.table_markers:
            marker_map[aid] = (c_p, 0.0, False)

        found_count = 0
        box_count = 0
        table_count = 0

        for i, marker_id_raw in enumerate(ids):
            aid = (
                int(marker_id_raw[0])
                if isinstance(marker_id_raw, (list, np.ndarray))
                else int(marker_id_raw)
            )

            if aid not in marker_map:
                continue

            corners_projector, height, is_box = marker_map[aid]
            corners_camera_current = corners_camera[i]  # (4, 2)

            if is_box:
                box_count += 1
            else:
                table_count += 1

            # For each corner (0-3):
            for j in range(4):
                projector_pixels = corners_projector[
                    j
                ]  # (2,) [u, v] in projector pixels
                # camera_pixels might be a list if it came from serialized state
                camera_pixels = np.array(
                    corners_camera_current[j], dtype=np.float32
                )  # (2,) [u, v] in camera pixels

                # 1. Undistort and convert to normalized camera coordinates
                point_normalized = cv2.undistortPoints(
                    camera_pixels.reshape(1, 1, 2),
                    camera_matrix,
                    distortion_coefficients,
                ).reshape(2)

                # 2. Convert to world ray
                ray_camera = np.array([point_normalized[0], point_normalized[1], 1.0])
                ray_world = rotation_matrix_camera.T @ ray_camera
                ray_world /= np.linalg.norm(ray_world)

                # 3. Intersect with plane Z = height
                if abs(ray_world[2]) < 1e-6:
                    continue  # Ray parallel to plane

                ray_distance = (height - camera_center_world[2]) / ray_world[2]
                world_point = camera_center_world + ray_distance * ray_world

                self.correspondences.append(
                    (
                        world_point.astype(np.float32),
                        projector_pixels.astype(np.float32),
                    )
                )
                found_count += 1

        logging.info(
            "Projector3DCalibrationScene: Captured %d points (%d box, %d table markers).",
            found_count,
            box_count,
            table_count,
        )

        if found_count > 0:
            self.current_box_pos_idx += 1
            logging.info(
                "Projector3DCalibrationScene: Step %d complete. Total accumulated points: %d",
                self.current_box_pos_idx,
                len(self.correspondences),
            )

            msg = f"Captured step {self.current_box_pos_idx}: {box_count} box, {table_count} table markers."
            if box_count == 0:
                msg += " (Warning: No box markers found!)"
            self.context.notifications.add_notification(msg)
        else:
            self.context.notifications.add_notification(
                "Capture failed: No markers detected."
            )

    def _run_calibration(self):
        """Solves for Projector Intrinsics and Extrinsics."""
        if not self.correspondences:
            logging.warning("No correspondences collected!")
            return

        from light_map.calibration_logic import calibrate_projector_3d

        projector_resolution = (
            self.context.app_config.width,
            self.context.app_config.height,
        )
        result = calibrate_projector_3d(self.correspondences, projector_resolution)

        if result:
            (
                intrinsic_matrix,
                distortion_coefficients,
                rotation_vector,
                translation_vector,
                rms,
            ) = result
            logging.info("Projector 3D Calibration Successful! RMS: %.3f", rms)
            # Save results
            ext_file = os.path.join(
                self.context.app_config.storage_manager.get_config_dir(),
                "projector_3d_calibration.npz",
            )
            np.savez(
                ext_file,
                intrinsic_matrix=intrinsic_matrix,
                distortion_coefficients=distortion_coefficients,
                rotation_vector=rotation_vector,
                translation_vector=translation_vector,
                rms=rms,
            )
            self.context.notifications.add_notification("3D Calibration Saved.")
        else:
            logging.error("Projector 3D Calibration Failed.")
            self.context.notifications.add_notification("Calibration Failed!")
