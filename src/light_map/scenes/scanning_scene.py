from __future__ import annotations

import time
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

import numpy as np

from light_map.common_types import SceneId, SessionData, ViewportState
from light_map.core.scene import Scene, SceneTransition
from light_map.session_manager import SessionManager
from light_map.token_tracker import TokenTracker

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.scene import HandInput


class ScanStage(Enum):
    START = auto()
    FLASH = auto()
    CAPTURE = auto()
    PROCESS = auto()
    SHOW_RESULT = auto()
    DONE = auto()


class ScanningScene(Scene):
    """Handles the token scanning sequence."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.token_tracker = TokenTracker()
        self._stage = ScanStage.START
        self._stage_start_time = 0.0
        self._last_scan_result_count = 0

    def on_enter(self, payload: dict | None = None) -> None:
        """Reset the state machine upon entering the scene."""
        self._stage = ScanStage.START
        self._stage_start_time = time.monotonic()
        self._last_scan_result_count = 0
        # self.token_tracker.debug_mode = self.context.app_config.debug_mode

    def update(
        self, inputs: List[HandInput], current_time: float
    ) -> Optional[SceneTransition]:
        """Runs the state machine for the scanning sequence."""
        elapsed_time = current_time - self._stage_start_time

        if self._stage == ScanStage.START:
            self._change_stage(ScanStage.FLASH, current_time)

        elif self._stage == ScanStage.FLASH:
            if elapsed_time > 1.5:  # 1.5s for camera to adjust
                self._change_stage(ScanStage.CAPTURE, current_time)

        elif self._stage == ScanStage.CAPTURE:
            # The capture itself happens in the render loop on the next frame
            # We transition immediately to processing.
            self._change_stage(ScanStage.PROCESS, current_time)

        elif self._stage == ScanStage.PROCESS:
            # Processing is synchronous and happens in `render`, so we move to results.
            self._change_stage(ScanStage.SHOW_RESULT, current_time)

        elif self._stage == ScanStage.SHOW_RESULT:
            if elapsed_time > 2.0:  # Show result for 2 seconds
                self._change_stage(ScanStage.DONE, current_time)
                return SceneTransition(SceneId.MAP)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the flash, or processes the frame for tokens."""
        if self._stage == ScanStage.FLASH or self._stage == ScanStage.CAPTURE:
            intensity = self.context.map_config_manager.get_flash_intensity()
            return np.full_like(frame, intensity, dtype=np.uint8)

        if self._stage == ScanStage.PROCESS:
            if self.context.last_camera_frame is not None:
                self._detect_and_save_tokens(self.context.last_camera_frame)
            else:
                print("Warning: No camera frame available for token detection.")

            # Immediately transition to avoid re-processing the same frame
            self._change_stage(ScanStage.SHOW_RESULT, time.monotonic())
            # Fall through to render results immediately

        if self._stage == ScanStage.SHOW_RESULT:
            # The main app loop will render the map, we just return the frame.
            # A notification or overlay with the count should be handled by a global overlay system.
            # For now, we'll notify and let the main app render the map.
            # The main app will need access to the ghost tokens from the context.
            return frame

        return np.zeros_like(frame, dtype=np.uint8)  # Default black screen

    def _detect_and_save_tokens(self, frame_white: np.ndarray):
        """Performs the actual token detection and session saving."""
        print("Scanning for tokens...")
        map_system = self.context.map_system
        map_config = self.context.map_config_manager

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

        tokens = self.token_tracker.detect_tokens(
            frame_white=frame_white,
            projector_matrix=self.context.projector_matrix,
            map_system=map_system,
            grid_spacing_svg=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            ppi=ppi,
        )

        self._last_scan_result_count = len(tokens)
        self.context.map_system.ghost_tokens = tokens  # Update context
        print(f"Detected {len(tokens)} tokens.")

        # Save Session
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
        # Assuming SessionManager is updated to handle map-specific sessions
        SessionManager.save_for_map(map_file, session)
        self.context.notifications.add_notification(f"Saved {len(tokens)} tokens.")

    def _change_stage(self, new_stage: ScanStage, current_time: float):
        self._stage = new_stage
        self._stage_start_time = current_time
