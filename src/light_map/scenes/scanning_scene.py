from __future__ import annotations

import time
import logging
import os
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

import numpy as np

from light_map.common_types import (
    Action,
    SceneId,
    SessionData,
    ViewportState,
    TokenDetectionAlgorithm,
)
from light_map.core.scene import Scene, SceneTransition
from light_map.session_manager import SessionManager
from light_map.token_tracker import TokenTracker

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput
    from light_map.interactive_app import InteractiveApp
    from light_map.common_types import Layer


class ScanStage(Enum):
    START = auto()

    # Flash Sequence
    FLASH = auto()
    CAPTURE_FLASH = auto()

    # Structured Light Sequence
    PREPARE_DARK = auto()
    WAIT_DARK = auto()
    CAPTURE_DARK = auto()
    PREPARE_PATTERN = auto()
    WAIT_PATTERN = auto()
    CAPTURE_PATTERN = auto()

    # Common
    PROCESS = auto()
    SHOW_RESULT = auto()
    DONE = auto()


class ScanningScene(Scene):
    """Handles the token scanning sequence."""

    @property
    def should_hide_overlays(self) -> bool:
        """Returns True if global overlays (debug, notification) should be hidden."""
        # Hide during critical capture stages
        return self._stage in [
            ScanStage.FLASH,
            ScanStage.CAPTURE_FLASH,
            ScanStage.PREPARE_DARK,
            ScanStage.WAIT_DARK,
            ScanStage.CAPTURE_DARK,
            ScanStage.PREPARE_PATTERN,
            ScanStage.WAIT_PATTERN,
            ScanStage.CAPTURE_PATTERN,
        ]

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.token_tracker = TokenTracker()
        self._stage = ScanStage.START
        self._stage_start_time = 0.0
        self._last_scan_result_count = 0

        # Data for Structured Light
        self._dark_frame: Optional[np.ndarray] = None
        self._pattern_frame: Optional[np.ndarray] = None
        self._pattern_image: Optional[np.ndarray] = None  # The image to project
        self._cached_pattern_points = []

    def on_enter(self, payload: dict | None = None) -> None:
        """Reset the state machine upon entering the scene."""
        self._stage = ScanStage.START
        self._stage_start_time = time.monotonic()
        self._last_scan_result_count = 0
        self._dark_frame = None
        self._pattern_frame = None
        self._pattern_image = None
        self._cached_pattern_points = []

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        """Runs the state machine for the scanning sequence."""
        elapsed_time = current_time - self._stage_start_time
        algorithm = self.context.map_config_manager.get_detection_algorithm()

        if self._stage == ScanStage.START:
            if algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT:
                self._change_stage(ScanStage.PREPARE_DARK, current_time)
            elif algorithm == TokenDetectionAlgorithm.ARUCO:
                self._change_stage(ScanStage.PROCESS, current_time)
            else:
                self._change_stage(ScanStage.FLASH, current_time)

        # --- Flash Sequence ---
        elif self._stage == ScanStage.FLASH:
            if elapsed_time > 1.5:  # 1.5s for camera to adjust
                self._change_stage(ScanStage.CAPTURE_FLASH, current_time)

        elif self._stage == ScanStage.CAPTURE_FLASH:
            # Capture happens in render/process transition.
            # For consistency with structured light, we grab frame here?
            # Actually, simpler to just hold state and let render/process grab it.
            # But existing code grabbed in PROCESS. Let's keep it simple.
            self._change_stage(ScanStage.PROCESS, current_time)

        # --- Structured Light Sequence ---
        elif self._stage == ScanStage.PREPARE_DARK:
            # Just a state to ensure we start rendering black
            self._change_stage(ScanStage.WAIT_DARK, current_time)

        elif self._stage == ScanStage.WAIT_DARK:
            if elapsed_time > 1.5:  # Increased for camera stability (auto-exposure)
                self._change_stage(ScanStage.CAPTURE_DARK, current_time)

        elif self._stage == ScanStage.CAPTURE_DARK:
            if self.context.last_camera_frame is not None:
                self._dark_frame = self.context.last_camera_frame.copy()
            self._change_stage(ScanStage.PREPARE_PATTERN, current_time)

        elif self._stage == ScanStage.PREPARE_PATTERN:
            # Generate pattern if not already
            if self._pattern_image is None:
                ppi = self.context.map_config_manager.get_ppi()
                width, height = (
                    self.context.app_config.width,
                    self.context.app_config.height,
                )

                # The pattern generation is now deterministic with its own seed
                self._pattern_image, self._cached_pattern_points = (
                    self.token_tracker.get_scan_pattern(width, height, ppi)
                )

            self._change_stage(ScanStage.WAIT_PATTERN, current_time)

        elif self._stage == ScanStage.WAIT_PATTERN:
            if elapsed_time > 1.5:  # Increased wait time for stability
                self._change_stage(ScanStage.CAPTURE_PATTERN, current_time)

        elif self._stage == ScanStage.CAPTURE_PATTERN:
            if self.context.last_camera_frame is not None:
                self._pattern_frame = self.context.last_camera_frame.copy()
            self._change_stage(ScanStage.PROCESS, current_time)

        # --- Common Processing ---
        elif self._stage == ScanStage.PROCESS:
            # Actual processing is triggered in render loop to ensure we aren't blocking update?
            # Actually existing code did it in render. Let's keep that pattern or move it here.
            # Moving to update might require it to be fast or async.
            # Use render call to trigger sync processing for now.
            pass

        elif self._stage == ScanStage.SHOW_RESULT:
            if elapsed_time > 2.0:  # Show result for 2 seconds
                self._change_stage(ScanStage.DONE, current_time)
                return SceneTransition(SceneId.MAP)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the flash, or processes the frame for tokens."""
        algorithm = self.context.map_config_manager.get_detection_algorithm()

        # --- Render Logic ---
        if self._stage == ScanStage.FLASH or self._stage == ScanStage.CAPTURE_FLASH:
            intensity = self.context.map_config_manager.get_flash_intensity()
            return np.full_like(frame, intensity, dtype=np.uint8)

        if self._stage in [
            ScanStage.PREPARE_DARK,
            ScanStage.WAIT_DARK,
            ScanStage.CAPTURE_DARK,
        ]:
            return np.zeros_like(frame, dtype=np.uint8)

        if self._stage in [
            ScanStage.PREPARE_PATTERN,
            ScanStage.WAIT_PATTERN,
            ScanStage.CAPTURE_PATTERN,
        ]:
            if self._pattern_image is not None:
                return self._pattern_image
            return np.zeros_like(frame, dtype=np.uint8)

        # --- Processing Logic ---
        if self._stage == ScanStage.PROCESS:
            frame_to_process = self.context.last_camera_frame

            if algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT:
                # We already captured frames
                frame_to_process = self._pattern_frame

            if frame_to_process is not None:
                self._detect_and_save_tokens(frame_to_process)
            else:
                logging.warning("No camera frame available for token detection.")

            # Immediately transition avoiding re-process
            self._change_stage(ScanStage.SHOW_RESULT, time.monotonic())
            # Fall through

        if self._stage == ScanStage.SHOW_RESULT:
            # Just return frame (likely map or last buffer).
            # Actually render returns what is projected.
            # We should probably project nothing (black) or the map?
            # If we return frame passed in, it assumes it's the underlying map.
            # The existing code returned 'frame' which is passed from InteractiveApp.render
            # usually containing the Map rendering.
            return frame

        return np.zeros_like(frame, dtype=np.uint8)

    def _detect_and_save_tokens(self, frame_white: np.ndarray):
        """Performs the actual token detection and session saving."""
        logging.info("Scanning for tokens...")
        map_system = self.context.map_system
        map_config = self.context.map_config_manager
        algorithm = map_config.get_detection_algorithm()

        # Update debug mode from context
        self.token_tracker.debug_mode = self.context.debug_mode

        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        map_file = ""

        if map_system.svg_loader:
            map_file = map_system.svg_loader.filename
            entry = map_config.data.maps.get(map_file)
            if entry:
                grid_spacing = entry.grid_spacing_svg
                grid_origin_x = entry.grid_origin_svg_x
                grid_origin_y = entry.grid_origin_svg_y

        ppi = map_config.get_ppi()
        token_configs = map_config.get_aruco_configs(map_file)

        # Sync calibration
        self.token_tracker.set_aruco_calibration(
            camera_matrix=self.context.app_config.camera_matrix,
            distortion_coefficients=self.context.app_config.distortion_coefficients,
            rotation_vector=self.context.app_config.rotation_vector,
            translation_vector=self.context.app_config.translation_vector,
        )

        tokens = self.token_tracker.detect_tokens(
            frame_white=frame_white,
            frame_pattern=self._pattern_frame,
            projector_matrix=self.context.app_config.projector_matrix,
            map_system=map_system,
            frame_dark=self._dark_frame,
            grid_spacing_svg=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            ppi=ppi,
            algorithm=algorithm,
            token_configs=token_configs,
            default_height_mm=25.0,  # Default for minis
            distortion_model=self.context.app_config.distortion_model,
        )

        self._last_scan_result_count = len(tokens)
        self.context.map_system.ghost_tokens = tokens  # Update context
        logging.info("Detected %d tokens.", len(tokens))

        if algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT:
            self.context.notifications.add_notification(
                f"SL Scan: Found {len(tokens)} tokens."
            )
        elif algorithm == TokenDetectionAlgorithm.ARUCO:
            self.context.notifications.add_notification(
                f"ArUco Scan: Found {len(tokens)} tokens."
            )
        else:
            self.context.notifications.add_notification(
                f"Flash Scan: Found {len(tokens)} tokens."
            )

        # Save Session
        if map_file:
            session = SessionData(
                map_file=map_file,
                viewport=ViewportState(
                    map_system.state.x,
                    map_system.state.y,
                    map_system.state.zoom,
                    map_system.state.rotation,
                ),
                tokens=tokens,
            )
            storage = self.context.app_config.storage_manager
            session_dir = None
            if storage:
                session_dir = os.path.join(storage.get_data_dir(), "sessions")
            SessionManager.save_for_map(map_file, session, session_dir=session_dir)
            logging.info("Session saved for %s", map_file)
        else:
            logging.info("No map loaded, session not saved to disk (memory only).")

    def _change_stage(self, new_stage: ScanStage, current_time: float):
        self._stage = new_stage
        self._stage_start_time = current_time

    @property
    def blocking(self) -> bool:
        """Scanning should be blocking during capture stages to avoid interference."""
        return self._stage not in [ScanStage.SHOW_RESULT, ScanStage.DONE]

    @property
    def show_tokens(self) -> bool:
        """Tokens should only be visible during results view."""
        return self._stage in [ScanStage.SHOW_RESULT, ScanStage.DONE]

    def get_active_layers(self, app: InteractiveApp) -> List[Layer]:
        """
        Scanning needs a black background during capture stages to avoid interference,
        but needs the map background to show results at the end.
        """
        if self._stage in [ScanStage.SHOW_RESULT, ScanStage.DONE]:
            return app.layer_stack

        # During capture: only show the scene layer (projector pattern/flash) + overlays
        return self.get_scene_with_ui_stack(app)
