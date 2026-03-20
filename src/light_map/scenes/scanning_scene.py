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
    TimerKey,
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
        self._last_scan_result_count = 0

        # Data for Structured Light
        self._dark_frame: Optional[np.ndarray] = None
        self._pattern_frame: Optional[np.ndarray] = None
        self._pattern_image: Optional[np.ndarray] = None  # The image to project
        self._cached_pattern_points = []

    def on_enter(self, payload: dict | None = None) -> None:
        """Reset the state machine upon entering the scene."""
        self._stage = ScanStage.START
        self._last_scan_result_count = 0
        self._dark_frame = None
        self._pattern_frame = None
        self._pattern_image = None
        self._cached_pattern_points = []
        # Clear any existing scanning timers
        self.context.events.cancel(TimerKey.SCANNING_STAGE)

    def on_exit(self) -> None:
        """Cleanup when leaving the scene."""
        self.context.events.cancel(TimerKey.SCANNING_STAGE)

    def update(
        self, inputs: List[HandInput], actions: List[Action], current_time: float
    ) -> Optional[SceneTransition]:
        """Runs the state machine for the scanning sequence."""
        algorithm = self.context.map_config_manager.get_detection_algorithm()

        if self._stage == ScanStage.START:
            if algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT:
                self._change_stage(ScanStage.PREPARE_DARK, current_time)
            elif algorithm == TokenDetectionAlgorithm.ARUCO:
                self._change_stage(ScanStage.PROCESS, current_time)
            else:
                self._change_stage(ScanStage.FLASH, current_time)

        # Transition logic for stages that have completed their processing or wait time
        if self._stage == ScanStage.DONE:
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

    def _on_stage_timer_expired(self):
        """Callback for when a stage timer finishes."""
        current_time = self.context.time_provider()

        if self._stage == ScanStage.FLASH:
            self._change_stage(ScanStage.CAPTURE_FLASH, current_time)

        elif self._stage == ScanStage.WAIT_DARK:
            self._change_stage(ScanStage.CAPTURE_DARK, current_time)

        elif self._stage == ScanStage.WAIT_PATTERN:
            self._change_stage(ScanStage.CAPTURE_PATTERN, current_time)

        elif self._stage == ScanStage.SHOW_RESULT:
            self._change_stage(ScanStage.DONE, current_time)

    def _change_stage(self, new_stage: ScanStage, current_time: float):
        """Transitions to a new stage and schedules next steps if necessary."""
        self._stage = new_stage

        # A. Trigger immediate processing for some stages
        if self._stage == ScanStage.CAPTURE_FLASH:
            # Flash capture: we could grab frame here or in PROCESS.
            # For simplicity and consistency, transition to process.
            self._change_stage(ScanStage.PROCESS, current_time)

        elif self._stage == ScanStage.PREPARE_DARK:
            self._change_stage(ScanStage.WAIT_DARK, current_time)

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

        elif self._stage == ScanStage.CAPTURE_PATTERN:
            if self.context.last_camera_frame is not None:
                self._pattern_frame = self.context.last_camera_frame.copy()
            self._change_stage(ScanStage.PROCESS, current_time)

        # B. Schedule future transitions for 'WAIT' or 'SHOW' stages
        delay = 0.0
        if self._stage == ScanStage.FLASH:
            delay = 1.5
        elif self._stage == ScanStage.WAIT_DARK:
            delay = 1.5
        elif self._stage == ScanStage.WAIT_PATTERN:
            delay = 1.5
        elif self._stage == ScanStage.SHOW_RESULT:
            delay = 2.0

        if delay > 0:
            self.context.events.schedule(
                delay, self._on_stage_timer_expired, key=TimerKey.SCANNING_STAGE
            )

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
