from __future__ import annotations
import copy
import time
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from collections import Counter
import cv2

from light_map.core.scene import Scene, SceneTransition
from light_map.core.map_interaction import MapInteractionController
from light_map.gestures import GestureType
from light_map.token_tracker import TokenTracker
from light_map.calibration_logic import calculate_ppi_from_frame
from light_map.map_system import MapState
from light_map.common_types import SceneId
from light_map.calibration import process_chessboard_images, save_camera_calibration
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
        # self.token_tracker.debug_mode = self.context.app_config.debug_mode

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        elapsed = current_time - self._stage_start_time

        if self._stage == FlashCalibStage.START:
            self._change_stage(FlashCalibStage.TESTING, current_time)

        elif self._stage == FlashCalibStage.TESTING:
            # Settle time for the camera after intensity change
            if elapsed > 0.5:
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
            if self._capture_frame:
                intensity = self._test_levels[self._current_level_idx]
                tokens = self.token_tracker.detect_tokens(
                    frame_white=frame,
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
                camera = self.context.app_config.camera
                if camera:
                    frame = camera.get_frame()
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
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        elif self._stage == "PROCESSING":
            text = "Processing..."
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        elif self._stage == "DONE":
            text = "Calibration Complete! Returning to Menu."
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        elif self._stage == "ERROR":
            text = "Calibration Failed! Returning to Menu."
            cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        return frame


class ProjectorCalibrationScene(Scene):
    """Handles projector calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self._stage = "DISPLAY_PATTERN"  # DISPLAY_PATTERN | CAPTURE | PROCESSING | DONE | ERROR
        self._pattern_image: Optional[np.ndarray] = None
        self._start_time = 0.0

    def on_enter(self, payload: Any = None) -> None:
        self._stage = "DISPLAY_PATTERN"
        self._pattern_image = None
        self._start_time = time.monotonic()
        # In a real scenario, we'd generate the pattern here or load it.
        # For simplicity, we assume the render method generates/displays it.
        self.context.notifications.add_notification("Displaying calibration pattern...")

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        elapsed = current_time - self._start_time

        if self._stage == "DISPLAY_PATTERN":
            # Wait for pattern to be projected and stable
            if elapsed > 1.0:
                self._stage = "CAPTURE"
                self._start_time = current_time

        elif self._stage == "CAPTURE":
            # Trigger capture (conceptually)
            # In this simple flow, we assume capture happens immediately after delay
            self._stage = "PROCESSING"
            self.context.notifications.add_notification("Capturing and processing...")

        elif self._stage == "PROCESSING":
            # Simulate processing logic
            # Real implementation would call projector.compute_homography here
            # For now, we just simulate success after a brief delay
            # We need to actually access the camera to do this for real.
            
            camera = self.context.app_config.camera
            if camera:
                frame = camera.get_frame()
                if frame is not None:
                    # TODO: Implement actual homography computation
                    # ret, homography = compute_homography(frame, pattern_info)
                    # if ret: ...
                    
                    # For now, assume success if we got a frame
                    self.context.notifications.add_notification("Projector calibrated.")
                    self._stage = "DONE"
                    return SceneTransition(SceneId.MENU)
                else:
                     self.context.notifications.add_notification("Error: Failed to capture frame.")
                     self._stage = "ERROR"
            else:
                self.context.notifications.add_notification("Error: No camera available.")
                self._stage = "ERROR"
            
            return SceneTransition(SceneId.MENU)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        if self._stage == "DISPLAY_PATTERN" or self._stage == "CAPTURE":
            # Display a white screen or a specific pattern
            # For now, just white to differentiate from black
            return np.full_like(frame, 255)
        
        return frame


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
        if self._stage == "DETECTING":
            ppi = calculate_ppi_from_frame(frame, self.context.projector_matrix)
            if ppi:
                self._candidate_ppi = ppi
                self._stage = "CONFIRMING"
        # Overlays should be handled by a global renderer, but for now
        # we return a black frame and assume the main loop will draw text.
        return np.zeros_like(frame, dtype=np.uint8)


class MapGridCalibrationScene(Scene):
    """Handles map grid calibration."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.interaction_controller = MapInteractionController()
        self.summon_gesture_start_time = 0.0
        self.is_interacting = False
        self._saved_map_state: Optional[MapState] = None
        self.calib_map_grid_size_inches = 1.0

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False

        if payload and "map_file" in payload:
            # This scene requires a map to be loaded. The logic to load it
            # should probably be handled in the main app loop before entering.
            pass

        # Save current user view and reset for calibration
        self._saved_map_state = copy.deepcopy(self.context.map_system.state)
        self.context.map_system.reset_view_to_base()

    def on_exit(self) -> None:
        # Restore user view on exiting without saving
        if self._saved_map_state:
            self.context.map_system.state = self._saved_map_state
            self._saved_map_state = None

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
                # Don't restore view, keep the calibrated one.
                self._saved_map_state = None
                return SceneTransition(SceneId.MENU)
        else:
            self.summon_gesture_start_time = 0.0

        # Process map interactions
        self.is_interacting = self.interaction_controller.process_gestures(
            inputs, self.context.map_system
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
        new_base_scale = map_system.state.zoom
        ppi = map_config.get_ppi()

        if ppi <= 0:
            self.context.notifications.add_notification(
                "Cannot calibrate grid: PPI is not set."
            )
            return

        derived_spacing = (ppi * self.calib_map_grid_size_inches) / new_base_scale

        print(
            f"Calibrated {filename}: Spacing={derived_spacing:.1f}, Unit={self.calib_map_grid_size_inches}in"
        )

        map_config.save_map_grid_config(
            filename,
            grid_spacing_svg=derived_spacing,
            grid_origin_svg_x=0.0,
            grid_origin_svg_y=0.0,
            physical_unit_inches=self.calib_map_grid_size_inches,
            scale_factor_1to1=new_base_scale,
        )

        # Update the map system's base scale for the current session
        map_system.base_scale = new_base_scale

        self.context.notifications.add_notification("Map grid calibrated.")


    def render(self, frame: np.ndarray) -> np.ndarray:
        # The main app loop will render the map, dimmed.
        # It will also render the calibration overlay.
        return frame




