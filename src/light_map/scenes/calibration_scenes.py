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
from light_map.common_types import SceneId, Action
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
        self._stage_start_time = 0.0
        self._test_levels = [255, 225, 195, 165, 135, 105, 75, 45]
        self._current_level_idx = 0
        self._results: Dict[int, int] = {}
        self._capture_frame = False
        self.is_dynamic = True

    def on_enter(self, payload: dict | None = None) -> None:
        self._stage = FlashCalibStage.START
        self._stage_start_time = time.monotonic()
        self._current_level_idx = 0
        self._results = {}
        self.token_tracker.debug_mode = self.context.debug_mode
        self.mark_dirty()

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        elapsed = current_time - self._stage_start_time

        if self._stage == FlashCalibStage.START:
            self._change_stage(FlashCalibStage.TESTING, current_time)

        elif self._stage == FlashCalibStage.TESTING:
            # Settle time for the camera after intensity change
            if elapsed > 1.5:
                self._capture_frame = True  # Signal render() to process a frame

        elif self._stage == FlashCalibStage.ANALYZING:
            self._analyze_results()
            self._change_stage(FlashCalibStage.SHOW_RESULT, current_time)

        elif self._stage == FlashCalibStage.SHOW_RESULT:
            if elapsed > 2.0:
                self._change_stage(FlashCalibStage.DONE, current_time)
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
        """Calibration scenes only need scene, UI, and cursor layers."""
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._stage == FlashCalibStage.TESTING:
            if self._capture_frame and self.context.last_camera_frame is not None:
                intensity = self._test_levels[self._current_level_idx]
                tokens = self.token_tracker.detect_tokens(
                    frame_white=self.context.last_camera_frame,
                    projector_matrix=self.context.projector_matrix,
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
                    # Reset timer for the next level's settle time
                    self._stage_start_time = time.monotonic()

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

    def _change_stage(self, new_stage: FlashCalibStage, current_time: float):
        self._stage = new_stage
        self._stage_start_time = current_time


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
        self.mark_dirty()
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
                (camera_matrix, dist_coeffs), _ = calibration_result
                storage = self.context.app_config.storage_manager
                output_file = (
                    storage.get_data_path("camera_calibration.npz")
                    if storage
                    else "camera_calibration.npz"
                )
                save_camera_calibration(
                    camera_matrix, dist_coeffs, output_file=output_file
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
        """Calibration scenes only need scene, UI, and cursor layers."""
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

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
        self._start_time = 0.0
        self.is_dynamic = True

    def on_enter(self, payload: Any = None) -> None:
        from light_map.projector import generate_calibration_pattern

        self._stage = "DISPLAY_PATTERN"
        self.mark_dirty()

        # Generate pattern
        w, h = self.context.app_config.width, self.context.app_config.height
        self._pattern_image, self._pattern_params = generate_calibration_pattern(
            w, h, pattern_rows=13, pattern_cols=18, border_size=30
        )
        self._start_time = time.monotonic()
        self.context.notifications.add_notification("Projecting calibration pattern...")

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        elapsed = current_time - self._start_time

        if self._stage == "DISPLAY_PATTERN":
            if elapsed > 1.0:  # Ensure it's being projected
                self._stage = "SETTLE"
                self._start_time = current_time

        elif self._stage == "SETTLE":
            if elapsed > 2.0:  # Camera settle time
                self._stage = "CAPTURE"

        elif self._stage == "CAPTURE":
            frame = self.context.last_camera_frame
            if frame is not None:
                self._stage = "PROCESSING"
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
                    self.context.projector_matrix = matrix
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

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """Calibration scenes only need scene, UI, and cursor layers."""
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
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
        self._rvec: Optional[np.ndarray] = None
        self._tvec: Optional[np.ndarray] = None
        self._token_heights: Dict[int, float] = {}
        self._token_sizes: Dict[int, int] = {}
        self._ground_points_cam: Optional[np.ndarray] = None
        self._ground_points_proj: Optional[np.ndarray] = None
        self._reprojection_error: float = 0.0
        self._obj_points: Optional[np.ndarray] = None
        self._img_points: Optional[np.ndarray] = None
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
        self.mark_dirty()
        self._ppi = self.context.map_config_manager.get_ppi()
        self._reprojection_error = 0.0
        self._obj_points = None
        self._img_points = None
        self._retry_gesture_start_time = 0.0
        self._current_time = 0.0
        self._known_targets = {}

        # Load ground points (Z=0) from projector calibration
        try:
            if os.path.exists("projector_calibration.npz"):
                data = np.load("projector_calibration.npz")
                self._ground_points_cam = data["camera_points"]
                self._ground_points_proj = data["projector_points"]
                logging.info(
                    "Loaded %d ground points from projector calibration.",
                    len(self._ground_points_cam),
                )
        except Exception as e:
            logging.error("Failed to load projector calibration points: %s", e)
            self._ground_points_cam = None
            self._ground_points_proj = None

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
                        pts_cam, self.context.projector_matrix
                    ).reshape(-1, 2)
                    px, py = pts_proj[0]

                    # Find nearest target zone
                    best_dist = 150.0  # Threshold in projector pixels
                    best_idx = -1
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

            # Use Fist to trigger capture if enough tokens
            if (
                valid_count >= 3
                and inputs
                and inputs[0].gesture == GestureType.CLOSED_FIST
            ):
                self._stage = "CAPTURE"

        elif self._stage == "CAPTURE":
            # Run solvePnP
            if self.context.camera_matrix is None:
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
                self.context.projector_matrix,
                self.context.camera_matrix,
                self.context.dist_coeffs,
                self._token_heights,
                self._ppi,
                ground_points_cam=self._ground_points_cam,
                ground_points_proj=self._ground_points_proj,
                known_targets=self._known_targets,
                aruco_corners=formatted_corners,
                aruco_ids=formatted_ids,
            )

            if result:
                self._rvec, self._tvec, self._obj_points, self._img_points = result

                # Calculate Reprojection Error
                projected_points, _ = cv2.projectPoints(
                    self._obj_points,
                    self._rvec,
                    self._tvec,
                    self.context.camera_matrix,
                    self.context.dist_coeffs,
                )
                projected_points = projected_points.reshape(-1, 2)

                errors = np.linalg.norm(self._img_points - projected_points, axis=1)
                self._reprojection_error = np.sqrt(np.mean(errors**2))

                self.context.notifications.add_notification(
                    f"Calibration Error: {self._reprojection_error:.2f} px"
                )
                self._stage = "VALIDATION"
            else:
                self.context.notifications.add_notification("Calibration failed.")
                self._stage = "PLACEMENT"

        elif self._stage == "VALIDATION":
            # Accept
            if inputs and inputs[0].gesture == GestureType.VICTORY:
                if self._rvec is not None and self._tvec is not None:
                    storage = self.context.app_config.storage_manager
                    output_file = (
                        storage.get_data_path("camera_extrinsics.npz")
                        if storage
                        else "camera_extrinsics.npz"
                    )
                    save_camera_extrinsics(
                        self._rvec, self._tvec, output_file=output_file
                    )
                    self.context.notifications.add_notification("Extrinsics saved.")
                return SceneTransition(SceneId.MENU)

            # Retry
            if inputs and inputs[0].gesture == GestureType.CLOSED_FIST:
                if self._retry_gesture_start_time == 0.0:
                    self._retry_gesture_start_time = current_time
                elif current_time - self._retry_gesture_start_time > 2.0:
                    self.context.notifications.add_notification(
                        "Calibration discarded."
                    )
                    self._stage = "PLACEMENT"
                    self._retry_gesture_start_time = 0.0
            else:
                self._retry_gesture_start_time = 0.0

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
        """Calibration scenes only need scene, UI, and cursor layers."""
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        current_time = self._current_time
        ppi = self._ppi if self._ppi > 0 else 96.0

        # Rendering Parameters for Cache Matching
        render_params = {
            "stage": self._stage,
            "target_status": self._target_status.copy(),
            "target_info": self._target_info.copy(),
            "has_reprojection": self._obj_points is not None,
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
                        (tx - half_size, ty - half_size - 10),
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

                # Center dot
                cv2.circle(canvas, (tx, ty), 3, (0, 0, 0), -1)

                # Label below
                draw_text_with_background(
                    canvas,
                    label,
                    (tx - half_size, ty + half_size + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color if thickness > 0 else (0, 100, 0),
                    1 if thickness > 0 else 2,
                )

            # Verification Overlay: Visual Feedback
            if (
                self._stage == "VALIDATION"
                and self._rvec is not None
                and self._tvec is not None
                and self._obj_points is not None
            ):
                # Calculate reprojected points (Camera Space)
                proj_pts_cam, _ = cv2.projectPoints(
                    self._obj_points,
                    self._rvec,
                    self._tvec,
                    self.context.camera_matrix,
                    self.context.dist_coeffs,
                )
                proj_pts_cam = proj_pts_cam.reshape(-1, 2)

                # Transform both sets to Projector Space for rendering
                img_pts_reshaped = self._img_points.reshape(-1, 1, 2)
                detected_proj = cv2.perspectiveTransform(
                    img_pts_reshaped, self.context.projector_matrix
                ).reshape(-1, 2)

                reprojected_proj = cv2.perspectiveTransform(
                    proj_pts_cam.reshape(-1, 1, 2), self.context.projector_matrix
                ).reshape(-1, 2)

                # Draw residuals
                for i in range(len(detected_proj)):
                    p_det = detected_proj[i]
                    p_rep = reprojected_proj[i]
                    error_px = np.linalg.norm(self._img_points[i] - proj_pts_cam[i])
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
        instr = (
            "Fist to calibrate (Need 3+ tokens)" if self._stage == "PLACEMENT" else ""
        )
        if self._stage == "VALIDATION":
            instr = "VICTORY to Accept, FIST (hold 2s) to Retry"
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
        """Calibration scenes only need scene, UI, and cursor layers."""
        return [
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

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
                    self.context.projector_matrix,
                    target_dist_mm=100.0,
                )
            elif 0 in flat_ids and 1 in flat_ids:
                # Re-format corners to (1, 4, 2) as expected by calculate_ppi_from_frame
                formatted_corners = tuple(np.array(c).reshape(1, 4, 2) for c in corners)
                formatted_ids = np.array(flat_ids)

                ppi = calculate_ppi_from_frame(
                    None,
                    self.context.projector_matrix,
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

    def __init__(self, start_spacing: float, width: int, height: int):
        self.spacing = start_spacing
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.width = width
        self.height = height

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
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False
        self.calib_map_grid_size_inches = 1.0
        self.grid_overlay: Optional[GridOverlay] = None
        self.is_dynamic = True

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False
        self.summon_gesture_start_time = 0.0
        self.mark_dirty()

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
                self.context.app_config.width,
                self.context.app_config.height,
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
                self.context.app_config.width,
                self.context.app_config.height,
            )

            # Center the grid initially
            self.grid_overlay.offset_x = self.context.app_config.width / 2
            self.grid_overlay.offset_y = self.context.app_config.height / 2
            logging.info("Initialized default grid (centered)")

    def on_exit(self) -> None:
        pass

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        primary_gesture = inputs[0].gesture if inputs else GestureType.NONE

        # Confirm gesture
        if primary_gesture == GestureType.VICTORY:
            if self.summon_gesture_start_time == 0:
                self.summon_gesture_start_time = current_time
            elif current_time - self.summon_gesture_start_time > 1.0:  # 1s hold
                self._save_calibration()
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

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
        return [
            app.map_layer,
            app.scene_layer,
            app.token_layer,
            app.menu_layer,
            app.notification_layer,
            app.debug_layer,
            app.cursor_layer,
        ]

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
