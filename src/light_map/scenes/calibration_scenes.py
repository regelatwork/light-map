from __future__ import annotations
import time
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import math
import numpy as np
import os
from collections import Counter
import cv2

from light_map.core.scene import Scene, SceneTransition
from light_map.core.map_interaction import MapInteractionController
from light_map.gestures import GestureType
from light_map.token_tracker import TokenTracker
from light_map.calibration_logic import calculate_ppi_from_frame, calibrate_extrinsics
from light_map.common_types import SceneId
from light_map.calibration import (
    process_chessboard_images,
    save_camera_calibration,
    save_camera_extrinsics,
)

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


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

    def on_enter(self, payload: dict | None = None) -> None:
        self._stage = FlashCalibStage.START
        self._stage_start_time = time.monotonic()
        self._current_level_idx = 0
        self._results = {}
        self.token_tracker.debug_mode = self.context.debug_mode

    def update(
        self, inputs: List[HandInput], current_time: float
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

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._stage == FlashCalibStage.TESTING:
            if self._capture_frame and self.context.last_camera_frame is not None:
                intensity = self._test_levels[self._current_level_idx]
                tokens = self.token_tracker.detect_tokens(
                    frame_white=self.context.last_camera_frame,
                    projector_matrix=self.context.projector_matrix,
                    map_system=self.context.map_system,
                )
                self._results[intensity] = len(tokens)
                print(f"Calibration: Level {intensity} -> Found {len(tokens)} tokens")
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
        print(msg)

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

    def on_enter(self, payload: Any = None) -> None:
        self._captured_images = []
        self._stage = "CAPTURE"
        self.context.notifications.add_notification(
            f"Capture {self._required_images} chessboard images."
        )

    def update(
        self, inputs: List[HandInput], current_time: float
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
                save_camera_calibration(camera_matrix, dist_coeffs)
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

    def render(self, frame: np.ndarray) -> np.ndarray:
        # Overlay instructions or status based on stage
        if self._stage == "CAPTURE":
            text = f"Capture {len(self._captured_images)}/{self._required_images} images (Fist)"
            cv2.putText(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
        elif self._stage == "PROCESSING":
            text = "Processing..."
            cv2.putText(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2
            )
        elif self._stage == "DONE":
            text = "Calibration Complete! Returning to Menu."
            cv2.putText(
                frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
            )
        elif self._stage == "ERROR":
            text = "Calibration Failed! Returning to Menu."
            cv2.putText(
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

    def on_enter(self, payload: Any = None) -> None:
        from light_map.projector import generate_calibration_pattern

        self._stage = "DISPLAY_PATTERN"

        # Generate pattern
        w, h = self.context.app_config.width, self.context.app_config.height
        self._pattern_image, self._pattern_params = generate_calibration_pattern(
            w, h, pattern_rows=13, pattern_cols=18, border_size=30
        )
        self._start_time = time.monotonic()
        self.context.notifications.add_notification("Projecting calibration pattern...")

    def update(
        self, inputs: List[HandInput], current_time: float
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
                    output_file = "projector_calibration.npz"
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
                    print(f"Homography error: {e}")
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

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._pattern_image is not None:
            return self._pattern_image
        return np.zeros_like(frame)


class ExtrinsicsCalibrationScene(Scene):
    """Handles camera extrinsics calibration (Camera Pose)."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "PLACEMENT"  # PLACEMENT | CAPTURE | VERIFY | DONE | ERROR
        self._target_zones: List[Tuple[int, int, int]] = []  # x, y, id
        self._detected_ids: Dict[int, Tuple[float, float]] = {}  # id -> (u, v) cam
        self._ppi = 0.0
        self._rvec: Optional[np.ndarray] = None
        self._tvec: Optional[np.ndarray] = None
        self._token_heights: Dict[int, float] = {}
        self._ground_points_cam: Optional[np.ndarray] = None
        self._ground_points_proj: Optional[np.ndarray] = None

    def on_enter(self, payload: Any = None) -> None:
        self._stage = "PLACEMENT"
        self._ppi = self.context.map_config_manager.get_ppi()

        # Load ground points (Z=0) from projector calibration
        try:
            if os.path.exists("projector_calibration.npz"):
                data = np.load("projector_calibration.npz")
                self._ground_points_cam = data["camera_points"]
                self._ground_points_proj = data["projector_points"]
                print(
                    f"Loaded {len(self._ground_points_cam)} ground points from projector calibration."
                )
        except Exception as e:
            print(f"Failed to load projector calibration points: {e}")
            self._ground_points_cam = None
            self._ground_points_proj = None

        # Load token heights from global config
        self._token_heights = {}
        for (
            aid,
            defn,
        ) in (
            self.context.map_config_manager.data.global_settings.aruco_defaults.items()
        ):
            resolved = self.context.map_config_manager.resolve_token_profile(aid)
            self._token_heights[aid] = resolved.height_mm

        # Define 5 Target Zones (in projector pixels)
        # Use a safe margin from edges
        w, h = self.context.app_config.width, self.context.app_config.height
        margin = 200
        self._target_zones = [
            (margin, margin, 10),  # TL
            (w - margin, margin, 11),  # TR
            (margin, h - margin, 12),  # BL
            (w - margin, h - margin, 13),  # BR
            (w // 2, h // 2, 14),  # C
        ]
        self.context.notifications.add_notification("Place tokens on target zones.")

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == "PLACEMENT":
            # Continuous detection (simulated via last_camera_frame in render)
            # Actually update logic should be here.

            # Detect markers
            frame = self.context.last_camera_frame
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
                parameters = cv2.aruco.DetectorParameters()
                detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
                corners, ids, rejected = detector.detectMarkers(gray)

                if ids is not None:
                    ids = ids.flatten()
                    self._detected_ids = {}
                    for i, aid in enumerate(ids):
                        if aid in self._token_heights:
                            c_cam = np.mean(corners[i][0], axis=0)
                            self._detected_ids[aid] = (c_cam[0], c_cam[1])

            # Validation: At least 3 targets are "covered"?
            # Actually, the user can use ANY known ID.
            valid_count = len(self._detected_ids)

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

            result = calibrate_extrinsics(
                self.context.last_camera_frame,
                self.context.projector_matrix,
                self.context.camera_matrix,
                self.context.dist_coeffs,
                self._token_heights,
                self._ppi,
                ground_points_cam=self._ground_points_cam,
                ground_points_proj=self._ground_points_proj,
                known_targets=None,  # For now, let H find the (X, Y) as in design
            )

            if result:
                self._rvec, self._tvec = result
                save_camera_extrinsics(self._rvec, self._tvec)
                self.context.notifications.add_notification("Extrinsics saved.")
                self._stage = "VERIFY"
            else:
                self.context.notifications.add_notification("Calibration failed.")
                self._stage = "PLACEMENT"

        elif self._stage == "VERIFY":
            # Use Victory to confirm
            if inputs and inputs[0].gesture == GestureType.VICTORY:
                return SceneTransition(SceneId.MENU)
            elif inputs and inputs[0].gesture == GestureType.OPEN_PALM:
                self._stage = "PLACEMENT"

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        canvas = np.full((h, w, 3), 200, dtype=np.uint8)  # Light gray "Arena"

        # Draw Target Zones
        for tx, ty, tid in self._target_zones:
            color = (0, 0, 255)  # Red
            # Check if ANY detected marker is "near" this target (in projector space)
            # Actually, let's just show detections and highlights
            cv2.circle(canvas, (tx, ty), 50, color, 2)
            cv2.putText(
                canvas,
                "Target",
                (tx - 30, ty + 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        # Highlight Detections (re-mapping from Camera to Projector)
        for aid, (cx, cy) in self._detected_ids.items():
            # Project to canvas
            pts_cam = np.array([[cx, cy]], dtype=np.float32).reshape(-1, 1, 2)
            pts_proj = cv2.perspectiveTransform(
                pts_cam, self.context.projector_matrix
            ).reshape(-1, 2)
            px, py = int(pts_proj[0][0]), int(pts_proj[0][1])

            if 0 <= px < w and 0 <= py < h:
                # Target ID green circle
                cv2.circle(canvas, (px, py), 40, (0, 255, 0), -1)
                cv2.putText(
                    canvas,
                    f"ID {aid}: {self._token_heights[aid]}mm",
                    (px - 50, py - 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 100, 0),
                    2,
                )

        # Verification Overlay: 3D Wireframes
        if (
            self._stage == "VERIFY"
            and self._rvec is not None
            and self._tvec is not None
        ):
            self._render_verification_boxes(canvas)

        # Instructions
        instr = (
            "Fist to calibrate (Need 3+ tokens)" if self._stage == "PLACEMENT" else ""
        )
        if self._stage == "VERIFY":
            instr = "Victory to accept, Palm to retry"
        cv2.putText(
            canvas, instr, (50, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2
        )

        return canvas

    def _render_verification_boxes(self, canvas: np.ndarray):
        """Draws 3D wireframe boxes where the camera thinks the tokens are."""
        if self.context.camera_matrix is None:
            return

        ppi_mm = self._ppi / 25.4

        for aid, (cx, cy) in self._detected_ids.items():
            h_mm = self._token_heights[aid]

            # Ground (X, Y) from H
            pts_cam = np.array([[cx, cy]], dtype=np.float32).reshape(-1, 1, 2)
            pts_proj = cv2.perspectiveTransform(
                pts_cam, self.context.projector_matrix
            ).reshape(-1, 2)
            px, py = pts_proj[0]
            wx, wy = px / ppi_mm, py / ppi_mm

            # 3D points of a box (mm)
            # Size 1 inch = 25.4 mm
            s = 25.4 / 2
            box_points = np.array(
                [
                    [wx - s, wy - s, 0],
                    [wx + s, wy - s, 0],
                    [wx + s, wy + s, 0],
                    [wx - s, wy + s, 0],
                    [wx - s, wy - s, h_mm],
                    [wx + s, wy - s, h_mm],
                    [wx + s, wy + s, h_mm],
                    [wx - s, wy + s, h_mm],
                ],
                dtype=np.float32,
            )

            # Project to Camera pixels
            img_pts, _ = cv2.projectPoints(
                box_points,
                self._rvec,
                self._tvec,
                self.context.camera_matrix,
                self.context.dist_coeffs,
            )

            # Now, project THESE camera pixels to Projector Pixels to draw them!
            img_pts = img_pts.reshape(-1, 1, 2)
            proj_pts = cv2.perspectiveTransform(
                img_pts, self.context.projector_matrix
            ).reshape(-1, 2)

            # Draw edges
            pts = proj_pts.astype(int)
            for i in range(4):
                cv2.line(canvas, tuple(pts[i]), tuple(pts[(i + 1) % 4]), (255, 0, 0), 2)
                cv2.line(
                    canvas,
                    tuple(pts[i + 4]),
                    tuple(pts[(i + 1) % 4 + 4]),
                    (255, 0, 0),
                    2,
                )
                cv2.line(canvas, tuple(pts[i]), tuple(pts[i + 4]), (255, 0, 0), 2)


class PpiCalibrationScene(Scene):
    """Handles PPI calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "DETECTING"  # DETECTING | CONFIRMING
        self._candidate_ppi = 0.0

    def on_enter(self, payload: Any = None) -> None:
        self._stage = "DETECTING"
        self._candidate_ppi = 0.0

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        if self._stage == "CONFIRMING" and inputs:
            gesture = inputs[0].gesture
            if gesture == GestureType.VICTORY:
                self.context.map_config_manager.set_ppi(self._candidate_ppi)
                self.context.notifications.add_notification(
                    f"PPI saved: {self._candidate_ppi:.2f}"
                )
                return SceneTransition(SceneId.MENU)
            elif gesture == GestureType.OPEN_PALM:
                self._stage = "DETECTING"
        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        canvas = np.full((h, w, 3), 255, dtype=np.uint8)  # White background

        # ArUco markers 0 and 1
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker0 = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
        marker1 = cv2.aruco.generateImageMarker(aruco_dict, 1, 100)

        # Convert to BGR
        marker0 = cv2.cvtColor(marker0, cv2.COLOR_GRAY2BGR)
        marker1 = cv2.cvtColor(marker1, cv2.COLOR_GRAY2BGR)

        # Place at centers, 100mm apart?
        # If we don't know PPI, we can't place them exactly 100mm apart.
        # Design doc says: "Ask the user to place two physical ArUco markers... at a known distance (e.g. 100mm)".
        # Wait, if the markers are projected, we know their distance in PROJECTOR PIXELS.
        # If we project them at px=200 and px=600, dist = 400px.
        # If the user places physical tokens on them, and we know tokens are 100mm apart.
        # Then PPI = 400px / (100mm / 25.4) = 101.6 PPI.

        # Let's project them at a fixed pixel distance.
        dist_px = 500
        cx, cy = w // 2, h // 2

        x0, y0 = cx - dist_px // 2, cy
        x1, y1 = cx + dist_px // 2, cy

        # Draw on canvas (with bounds check)
        for x, y, marker in [(x0, y0, marker0), (x1, y1, marker1)]:
            y1_idx, y2_idx = max(0, y - 50), min(h, y + 50)
            x1_idx, x2_idx = max(0, x - 50), min(w, x + 50)

            # Sub-marker crop if at edges
            m_y1 = 50 - (y - y1_idx)
            m_y2 = m_y1 + (y2_idx - y1_idx)
            m_x1 = 50 - (x - x1_idx)
            m_x2 = m_x1 + (x2_idx - x1_idx)

            if y2_idx > y1_idx and x2_idx > x1_idx:
                canvas[y1_idx:y2_idx, x1_idx:x2_idx] = marker[m_y1:m_y2, m_x1:m_x2]

        # Text instructions
        cv2.putText(
            canvas,
            "Place markers 100mm apart on targets.",
            (cx - 200, cy + 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
        )

        if self._stage == "DETECTING":
            if self.context.last_camera_frame is not None:
                # We need to tell calculate_ppi_from_frame that the PROJECTOR distance is dist_px
                # Wait, calculate_ppi_from_frame assumes it knows the PHYSICAL distance (100mm)
                # and finds the PROJECTOR distance by detection.
                ppi = calculate_ppi_from_frame(
                    self.context.last_camera_frame,
                    self.context.projector_matrix,
                    target_dist_mm=100.0,
                )
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
                (cx - 150, cy - 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 150, 0),
                2,
            )
            cv2.putText(
                canvas,
                "VICTORY to save, PALM to retry",
                (cx - 150, cy + 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 0),
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

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False
        self.summon_gesture_start_time = 0.0

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
            print(
                f"Restored grid for {filename}: spacing={start_spacing:.1f}, offset=({sx:.1f}, {sy:.1f})"
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
            print("Initialized default grid (centered)")

    def on_exit(self) -> None:
        pass

    def update(
        self, inputs: List[HandInput], current_time: float
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

        print(
            f"Calibrated {filename}: Spacing={derived_spacing_svg:.1f}, Origin=({wx:.1f}, {wy:.1f})"
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
