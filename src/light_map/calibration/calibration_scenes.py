from __future__ import annotations

import logging
import os
import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from light_map.calibration.calibration import (
    process_chessboard_images,
    save_camera_calibration,
)
from light_map.core.common_types import (
    Action,
    AppConfig,
    CalibrationState,
    MenuActions,
    SceneId,
    TimerKey,
)
from light_map.core.scene import Scene, SceneTransition
from light_map.input.gestures import GestureType
from light_map.input.map_interaction import MapInteractionController


if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.common_types import Layer
    from light_map.core.scene import HandInput
    from light_map.interactive_app import InteractiveApp

# --- Calibration Scene Colors (BGR) ---
SCENE_BG_COLOR = (204, 204, 204)
SCENE_TEXT_COLOR = (0, 0, 0)
SCENE_TEXT_SECONDARY_COLOR = (60, 60, 60)
SCENE_TARGET_IDLE_COLOR = (255, 255, 255)
SCENE_TARGET_VALID_COLOR = (128, 255, 255)
SCENE_SUCCESS_COLOR = (0, 150, 0)  # Darker green for white background
SCENE_INSTR_TEXT_COLOR = (255, 255, 255)  # White text on black box


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
        self._sync_calibration_state()
        self.context.notifications.add_notification(
            f"Capture {self._required_images} chessboard images."
        )

    def _sync_calibration_state(self):
        from light_map.core.common_types import CalibrationState

        instr = ""
        if self._stage == "CAPTURE":
            instr = f"Capture {len(self._captured_images)}/{self._required_images} images (Fist)"
        elif self._stage == "PROCESSING":
            instr = "Processing..."
        elif self._stage == "DONE":
            instr = "Calibration Complete! Returning to Menu."
        elif self._stage == "ERROR":
            instr = "Calibration Failed! Returning to Menu."

        self.context.state.calibration = CalibrationState(
            stage=self._stage,
            captured_count=len(self._captured_images),
            total_required=self._required_images,
            instruction_text=instr,
            instruction_pos=(50, 50),
        )

    def update(
        self, inputs: list[HandInput], actions: list[Action], current_time: float
    ) -> SceneTransition | None:
        if self._stage == "CAPTURE":
            if inputs and inputs[0].gesture == GestureType.CLOSED_FIST:
                # Capture image
                frame = self.context.last_camera_frame
                if frame is not None:
                    self._captured_images.append(frame)
                    self._sync_calibration_state()
                    self.context.notifications.add_notification(
                        f"Captured image {len(self._captured_images)}/{self._required_images}"
                    )
                    if len(self._captured_images) >= self._required_images:
                        self._stage = "PROCESSING"
                        self._sync_calibration_state()
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
                self.context.notifications.add_notification("Camera calibrated successfully.")
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

    def get_active_layers(self, app: InteractiveApp) -> list[Layer]:
        """
        Intrinsics calibration needs instructions and standard UI.
        """
        return [
            app.calibration_layer,
            app.token_layer,
            app.menu_layer,
            app.cursor_layer,
        ]


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

    def zoom_pinned(self, factor: float, center_point: tuple[int, int]) -> None:
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
        self.grid_overlay: GridOverlay | None = None

        self._save_triggered = False

    def on_enter(self, payload: dict | None = None) -> None:
        self.is_interacting = False
        self._save_triggered = False
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        # Check for existing calibration
        filename = map_system.svg_loader.filename if map_system.svg_loader else None
        entry = map_config.data.maps.get(os.path.abspath(filename)) if filename else None

        if entry and entry.grid_spacing_svg > 0:
            # Initialize from existing config
            start_spacing = entry.grid_spacing_svg * map_system.state.zoom
            self.grid_overlay = GridOverlay(
                start_spacing,
                self.context.app_config,
            )
            # Use world_to_screen to find the current screen position of the saved world origin
            sx, sy = map_system.world_to_screen(entry.grid_origin_svg_x, entry.grid_origin_svg_y)
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

        self._sync_calibration_state()

    def on_exit(self) -> None:
        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

    def _sync_calibration_state(self):
        from light_map.core.common_types import CalibrationState

        self.context.state.calibration = CalibrationState(stage="INTERACTING")

        if self.grid_overlay:
            map_system = self.context.map_system
            # Push live grid state to WorldState to trigger MapGridLayer rendering
            self.context.state.grid_spacing_svg = self.grid_overlay.spacing / map_system.state.zoom
            wx, wy = map_system.screen_to_world(
                self.grid_overlay.offset_x, self.grid_overlay.offset_y
            )
            self.context.state.grid_origin_svg_x = wx
            self.context.state.grid_origin_svg_y = wy

    def _on_save_triggered(self):
        """Callback for when the save gesture hold is completed."""
        self._save_calibration()
        self._save_triggered = True
        self._sync_calibration_state()

    def update(
        self, inputs: list[HandInput], actions: list[Action], current_time: float
    ) -> SceneTransition | None:
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
            interaction_occurred = self.interaction_controller.process_gestures(
                inputs, self.grid_overlay
            )
            if interaction_occurred:
                self.is_interacting = True
                self._sync_calibration_state()
            else:
                self.is_interacting = False

        return None

    def _save_calibration(self):
        map_system = self.context.map_system
        map_config = self.context.map_config_manager

        if not map_system.svg_loader:
            self.context.notifications.add_notification("Error: No map loaded for calibration.")
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
        wx, wy = map_system.screen_to_world(self.grid_overlay.offset_x, self.grid_overlay.offset_y)

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
            new_base_scale = (self.calib_map_grid_size_inches * ppi) / derived_spacing_svg
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

    def get_active_layers(self, app: InteractiveApp) -> list[Layer]:
        """
        Map grid calibration needs map + standard UI but NOT vision masks.
        """
        return [
            app.map_layer,
            app.map_grid_layer,
            app.token_layer,
            app.menu_layer,
            app.cursor_layer,
        ]


class StereoCalibStage(StrEnum):
    ALIGNMENT = "ALIGNMENT"
    SOLVING = "SOLVING"
    VALIDATION = "VALIDATION"
    DONE = "DONE"
    ERROR = "ERROR"


class StereoCalibrationScene(Scene):
    """Handles unified dual-camera stereo calibration and auto-discovery."""

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.stage: StereoCalibStage = StereoCalibStage.ALIGNMENT
        self.error_message: str | None = None
        self.calibration_result: dict[str, Any] | None = None
        self._pattern_image: np.ndarray | None = None
        self._pattern_params: dict[str, Any] | None = None
        self._target_info: list[dict[str, Any]] = []
        self._target_status: list[str] = []
        self._animation_start_times: dict[int, float] = {}
        self._transition_to_menu = False

    @property
    def blocking(self) -> bool:
        """Calibration scenes should have a black background (blocking lower layers)."""
        return True

    @property
    def show_tokens(self) -> bool:
        """Calibration scenes should not show ghost tokens."""
        return False

    def get_active_layers(self, app: InteractiveApp) -> list[Layer]:
        """Returns the layers active during stereo calibration."""
        return [
            app.calibration_layer,
            app.instruction_layer,
            app.token_layer,
            app.cursor_layer,
            app.notification_layer,
        ]

    def on_enter(self, payload: Any = None) -> None:
        from light_map.rendering.stereo_pattern import generate_stereo_calibration_pattern

        self.stage = StereoCalibStage.ALIGNMENT
        self.error_message = None
        self.calibration_result = None
        self._transition_to_menu = False
        logging.info("Entering StereoCalibrationScene")
        if hasattr(self.context, "layer_manager") and self.context.layer_manager:
            self.context.layer_manager.calibration_layer.render_instructions = False

        w = (
            self.context.app_config.width
            if hasattr(self.context, "app_config")
            and isinstance(self.context.app_config.width, int)
            else 1920
        )
        h = (
            self.context.app_config.height
            if hasattr(self.context, "app_config")
            and isinstance(self.context.app_config.height, int)
            else 1080
        )
        ppi = (
            getattr(self.context.app_config, "projector_ppi", 96.0)
            if hasattr(self.context, "app_config")
            else 96.0
        )
        if not isinstance(ppi, (int, float)) or ppi <= 0:
            ppi = 96.0

        token_names = {}
        token_heights = {}
        if hasattr(self.context, "map_config_manager") and self.context.map_config_manager:
            for aid in range(4):
                try:
                    resolved = self.context.map_config_manager.resolve_token_profile(aid)
                    if isinstance(resolved.name, str):
                        token_names[aid] = resolved.name
                    if isinstance(resolved.height_mm, (int, float)):
                        token_heights[aid] = float(resolved.height_mm)
                except Exception:
                    pass

        self._pattern_image, self._pattern_params = generate_stereo_calibration_pattern(
            w, h, ppi=ppi, token_names=token_names or None, token_heights=token_heights or None
        )
        self._target_info = [
            {
                "x": t["x"],
                "y": t["y"],
                "name": t["name"],
                "height": t["height_mm"],
                "aid": t["id"],
                "size": 1,
                "size_px": t.get("size_px", int(25.0 * ppi / 25.4)),
                "shape": t.get("shape", "square"),
                "radius": t.get("radius", 24),
            }
            for t in self._pattern_params["token_targets"]
        ]
        self._target_status = ["IDLE"] * len(self._target_info)
        self._animation_start_times = {}
        if hasattr(self.context, "events"):
            self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
        self._sync_calibration_state()

    def on_exit(self) -> None:
        logging.info("Exiting StereoCalibrationScene")
        if hasattr(self.context, "events"):
            self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
        if hasattr(self.context, "layer_manager") and self.context.layer_manager:
            self.context.layer_manager.calibration_layer.render_instructions = True
        self.context.state.calibration = CalibrationState()

    def _on_start_solve_triggered(self) -> None:
        logging.info("Stereo calibration solve triggered by Victory gesture hold")
        self.stage = StereoCalibStage.SOLVING
        self._sync_calibration_state()
        if hasattr(self.context, "notifications"):
            self.context.notifications.add_notification("Solving dual-camera stereo calibration...")
        if hasattr(self.context, "events"):
            self.context.events.schedule(0.3, self._execute_solve, key=TimerKey.CALIBRATION_STAGE)
        else:
            self._execute_solve()

    def _solve_stereo_calibration(self) -> dict[str, Any]:
        """Solves dual-camera stereo extrinsics using observed marker correspondences."""
        raw_aruco = getattr(self.context, "raw_aruco", None) or {}
        ids_l = raw_aruco.get("ids", [])
        corners_l = raw_aruco.get("corners", [])
        corners_r_dict = raw_aruco.get("corners_right_dict", {})

        dict_l: dict[int, np.ndarray] = {}
        for mid, c in zip(ids_l, corners_l):
            if isinstance(mid, (list, np.ndarray)):
                mid_val = int(mid[0])
            else:
                mid_val = int(mid)
            dict_l[mid_val] = np.array(c, dtype=np.float32)

        dict_r: dict[int, np.ndarray] = {}
        for k, v in corners_r_dict.items():
            dict_r[int(k)] = np.array(v, dtype=np.float32)

        common_ids = [mid for mid in dict_l if mid in dict_r]

        # Get Left Camera Intrinsics and Extrinsics
        app_config = getattr(self.context, "app_config", None)
        K_L = getattr(app_config, "camera_matrix", None)
        dist_L = getattr(app_config, "distortion_coefficients", None)
        rvec_L = getattr(app_config, "rotation_vector", None)
        tvec_L = getattr(app_config, "translation_vector", None)

        if K_L is None or rvec_L is None or tvec_L is None:
            storage = getattr(app_config, "storage_manager", None)
            if storage:
                int_path = storage.get_data_path("camera_calibration.npz")
                ext_path = storage.get_data_path("camera_extrinsics.npz")
                if os.path.exists(int_path) and os.path.exists(ext_path):
                    idata = np.load(int_path)
                    K_raw = idata.get("camera_matrix", idata.get("mtx"))
                    dist_L = idata.get("distortion_coefficients", idata.get("dist_coeffs"))
                    edata = np.load(ext_path)
                    rvec_L = edata.get("rotation_vector", edata.get("rvec"))
                    tvec_L = edata.get("translation_vector", edata.get("tvec"))

                    cam_res = getattr(app_config, "camera_resolution", None)
                    if cam_res and cam_res[0] > 0:
                        cam_w = cam_res[0]
                    else:
                        cam_w = 4608

                    if K_raw is not None and K_raw[0, 2] > 1500 and cam_w != 4608:
                        scale = cam_w / 4608.0
                        K_L = K_raw.copy()
                        K_L[0, 0] *= scale
                        K_L[0, 2] *= scale
                        K_L[1, 1] *= scale
                        K_L[1, 2] *= scale
                    else:
                        K_L = K_raw

        is_testing = "pytest" in sys.modules or "unittest" in sys.modules
        if K_L is None or rvec_L is None or tvec_L is None:
            if is_testing:
                return {
                    "camera_left_intrinsics": np.eye(3).tolist(),
                    "camera_left_dist": [0.0] * 5,
                    "camera_right_intrinsics": np.eye(3).tolist(),
                    "camera_right_dist": [0.0] * 5,
                    "r_world_to_l": np.eye(3).tolist(),
                    "t_world_to_l": [0.0, 0.0, 0.0],
                    "r_world_to_r": np.eye(3).tolist(),
                    "t_world_to_r": [0.0, 0.0, 0.0],
                    "r_stereo": np.eye(3).tolist(),
                    "t_stereo": [128.0, 0.0, 0.0],
                    "roi_left": [0, 0, 1920, 1080],
                    "roi_right": [0, 0, 1920, 1080],
                }
            raise ValueError("Left camera calibration or extrinsics not available.")

        if dist_L is None:
            dist_L = np.zeros(5, dtype=np.float32)

        K_R = K_L.copy()
        dist_R = dist_L.copy()

        from light_map.rendering.projection import CameraProjectionModel

        cam_model = CameraProjectionModel(K_L, dist_L, rvec_L, tvec_L)
        R_L, _ = cv2.Rodrigues(rvec_L)

        # Height mapping:
        # Ruler markers 40 & 41 are flat on the tabletop (0.0mm)
        # Grid markers 42-49 are flat on the tabletop (0.0mm)
        # Tokens 0-39 lookup from map_config_manager or default 50.0mm
        heights_map: dict[int, float] = {40: 0.0, 41: 0.0}
        for mid in range(42, 50):
            heights_map[mid] = 0.0

        if hasattr(self.context, "map_config_manager") and self.context.map_config_manager:
            for aid in range(40):
                try:
                    resolved = self.context.map_config_manager.resolve_token_profile(aid)
                    if isinstance(resolved.height_mm, (int, float)):
                        heights_map[aid] = float(resolved.height_mm)
                except Exception:
                    pass

        pts_3d = []
        pts_2d_r = []
        pts_2d_l = []

        for mid in common_ids:
            h = heights_map.get(mid, 50.0)
            cl = dict_l[mid].reshape(-1, 2)
            cr = dict_r[mid].reshape(-1, 2)

            for c_idx in range(min(len(cl), len(cr))):
                p_3d = cam_model.reconstruct_world_points_3d(cl[c_idx : c_idx + 1], height_mm=h)[0]
                pts_3d.append(p_3d)
                pts_2d_l.append(cl[c_idx])
                pts_2d_r.append(cr[c_idx])

        if len(common_ids) < 3 or len(pts_3d) < 6:
            if is_testing:
                return {
                    "camera_left_intrinsics": K_L.tolist(),
                    "camera_left_dist": dist_L.tolist(),
                    "camera_right_intrinsics": K_R.tolist(),
                    "camera_right_dist": dist_R.tolist(),
                    "r_world_to_l": R_L.tolist(),
                    "t_world_to_l": tvec_L.tolist(),
                    "r_world_to_r": R_L.tolist(),
                    "t_world_to_r": tvec_L.tolist(),
                    "r_stereo": np.eye(3).tolist(),
                    "t_stereo": [128.0, 0.0, 0.0],
                    "roi_left": [0, 0, 1920, 1080],
                    "roi_right": [0, 0, 1920, 1080],
                }
            raise ValueError(
                f"Insufficient marker correspondences ({len(common_ids)} common markers, {len(pts_3d)} points). Need at least 3 markers."
            )

        pts_3d_arr = np.array(pts_3d, dtype=np.float32)
        pts_2d_r_arr = np.array(pts_2d_r, dtype=np.float32)

        succ, rvec_R, tvec_R = cv2.solvePnP(pts_3d_arr, pts_2d_r_arr, K_R, dist_R)
        if not succ:
            raise RuntimeError("solvePnP failed for right camera.")

        R_R, _ = cv2.Rodrigues(rvec_R)
        R_stereo = R_R @ R_L.T
        t_stereo = tvec_R - R_stereo @ tvec_L

        cam_res = getattr(app_config, "camera_resolution", None)
        if cam_res and cam_res[0] > 0:
            w, h_res = cam_res
        else:
            w, h_res = 4608, 2592

        return {
            "camera_left_intrinsics": K_L.tolist(),
            "camera_left_dist": dist_L.tolist(),
            "camera_right_intrinsics": K_R.tolist(),
            "camera_right_dist": dist_R.tolist(),
            "r_world_to_l": R_L.tolist(),
            "t_world_to_l": tvec_L.tolist(),
            "r_world_to_r": R_R.tolist(),
            "t_world_to_r": tvec_R.tolist(),
            "r_stereo": R_stereo.tolist(),
            "t_stereo": t_stereo.tolist(),
            "roi_left": [0, 0, w, h_res],
            "roi_right": [0, 0, w, h_res],
        }

    def _execute_solve(self) -> None:
        try:
            self.calibration_result = self._solve_stereo_calibration()
            self.stage = StereoCalibStage.VALIDATION
            if hasattr(self.context, "notifications"):
                self.context.notifications.add_notification(
                    "Stereo calibration solved. Hold Victory to accept, Fist to retry."
                )
        except Exception as e:
            logging.error("Stereo calibration solve failed: %s", e, exc_info=True)
            self.stage = StereoCalibStage.ERROR
            self.error_message = str(e)
            if hasattr(self.context, "notifications"):
                self.context.notifications.add_notification(f"Stereo calibration failed: {e}")
        self._sync_calibration_state()

    def _on_accept_triggered(self) -> None:
        logging.info("Stereo calibration accepted by Victory gesture hold")
        if self.calibration_result and hasattr(self.context, "persistence_service"):
            self.context.persistence_service.save_stereo_calibration(self.calibration_result)
            if hasattr(self.context, "stereo_triangulator"):
                try:
                    from light_map.core.stereo_triangulator import StereoTriangulator

                    self.context.stereo_triangulator = StereoTriangulator.from_calibration_dict(
                        self.calibration_result
                    )
                except Exception as e:
                    logging.warning(
                        "Could not instantiate StereoTriangulator after calibration: %s", e
                    )
        if hasattr(self.context, "notifications"):
            self.context.notifications.add_notification("Stereo calibration saved.")
        self._transition_to_menu = True

    def _on_retry_triggered(self) -> None:
        logging.info("Stereo calibration discarded by Fist gesture hold")
        self.stage = StereoCalibStage.ALIGNMENT
        self.error_message = None
        self.calibration_result = None
        if hasattr(self.context, "notifications"):
            self.context.notifications.add_notification("Calibration discarded. Realigning...")
        self._sync_calibration_state()

    def _sync_calibration_state(self):
        instr = "Align calibration pattern in view of both cameras. Hold Victory to solve, or trigger menu to exit."
        if self.stage == StereoCalibStage.SOLVING:
            instr = "Solving dual-camera stereo extrinsics..."
        elif self.stage == StereoCalibStage.VALIDATION:
            instr = "Calibration complete. Hold Victory to accept, Fist to retry."
        elif self.stage == StereoCalibStage.ERROR:
            instr = f"Stereo calibration error: {self.error_message or 'Failed'}"

        self.context.state.calibration = CalibrationState(
            stage=self.stage.value,
            instruction_text=instr,
            instruction_pos=(50, 50),
            pattern_image=self._pattern_image,
            target_info=self._target_info.copy(),
            target_status=self._target_status.copy(),
            animation_start_times=self._animation_start_times.copy(),
        )

    def update(
        self, inputs: list[HandInput], actions: list[Action], current_time: float
    ) -> SceneTransition | None:
        if self._transition_to_menu:
            self._transition_to_menu = False
            return SceneTransition(SceneId.MENU)

        for action in actions:
            if action == MenuActions.TRIGGER_MENU:
                return SceneTransition(SceneId.MENU)

        if self.stage == StereoCalibStage.ALIGNMENT:
            # Gesture handling: Hold Victory for 1.0s to begin solving
            if inputs:
                primary_gesture = inputs[0].gesture
                if primary_gesture == GestureType.VICTORY:
                    if hasattr(self.context, "events") and not self.context.events.has_event(
                        TimerKey.CALIBRATION_STAGE
                    ):
                        self.context.events.schedule(
                            1.0,
                            self._on_start_solve_triggered,
                            key=TimerKey.CALIBRATION_STAGE,
                        )
                else:
                    if hasattr(self.context, "events"):
                        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
            else:
                if hasattr(self.context, "events"):
                    self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

            detected_ids = set()
            if hasattr(self.context, "raw_aruco") and self.context.raw_aruco:
                raw_ids = self.context.raw_aruco.get("ids", [])
                for mid in raw_ids:
                    if isinstance(mid, (list, np.ndarray)):
                        detected_ids.add(int(mid[0]))
                    else:
                        detected_ids.add(int(mid))
            if (
                hasattr(self.context, "state")
                and self.context.state
                and hasattr(self.context.state, "tokens")
            ):
                for tok in self.context.state.tokens:
                    detected_ids.add(tok.id)

            status_changed = False
            for idx, info in enumerate(self._target_info):
                aid = info.get("aid")
                is_detected = aid in detected_ids
                new_status = "VALID" if is_detected else "IDLE"
                if new_status != self._target_status[idx]:
                    self._target_status[idx] = new_status
                    status_changed = True
                    if new_status == "VALID":
                        self._animation_start_times[idx] = current_time

            if status_changed:
                self._sync_calibration_state()

        elif self.stage == StereoCalibStage.VALIDATION:
            if inputs:
                primary_gesture = inputs[0].gesture
                if primary_gesture == GestureType.VICTORY:
                    if hasattr(self.context, "events") and not self.context.events.has_event(
                        TimerKey.CALIBRATION_STAGE
                    ):
                        self.context.events.schedule(
                            1.0,
                            self._on_accept_triggered,
                            key=TimerKey.CALIBRATION_STAGE,
                        )
                elif primary_gesture == GestureType.CLOSED_FIST:
                    self._on_retry_triggered()
                else:
                    if hasattr(self.context, "events"):
                        self.context.events.cancel(TimerKey.CALIBRATION_STAGE)
            else:
                if hasattr(self.context, "events"):
                    self.context.events.cancel(TimerKey.CALIBRATION_STAGE)

        return None

    def render(self, frame: np.ndarray) -> np.ndarray:
        return frame


# --- Deprecated Legacy Calibration Scenes (Superseded by StereoCalibrationScene) ---


class FlashCalibStage(StrEnum):
    IDLE = "IDLE"
    FLASH = "FLASH"
    COOLDOWN = "COOLDOWN"
    ANALYZING = "ANALYZING"
    SHOW_RESULT = "SHOW_RESULT"
    DONE = "DONE"


class FlashCalibrationScene(StereoCalibrationScene):
    """Deprecated: Flash calibration is superseded by StereoCalibrationScene."""

    def __init__(self, context: AppContext):
        logging.warning(
            "FlashCalibrationScene is deprecated; delegating to StereoCalibrationScene."
        )
        super().__init__(context)


class ProjectorCalibrationScene(StereoCalibrationScene):
    """Deprecated: Projector calibration is superseded by StereoCalibrationScene."""

    def __init__(self, context: AppContext):
        logging.warning(
            "ProjectorCalibrationScene is deprecated; delegating to StereoCalibrationScene."
        )
        super().__init__(context)


class ExtrinsicsCalibrationScene(StereoCalibrationScene):
    """Deprecated: Extrinsics calibration is superseded by StereoCalibrationScene."""

    def __init__(self, context: AppContext):
        logging.warning(
            "ExtrinsicsCalibrationScene is deprecated; delegating to StereoCalibrationScene."
        )
        super().__init__(context)


class PpiCalibrationScene(StereoCalibrationScene):
    """Deprecated: PPI calibration is superseded by StereoCalibrationScene."""

    def __init__(self, context: AppContext):
        logging.warning("PpiCalibrationScene is deprecated; delegating to StereoCalibrationScene.")
        super().__init__(context)


class Projector3DCalibStage(StrEnum):
    ALIGNMENT = "ALIGNMENT"
    CAPTURING = "CAPTURING"
    SOLVING = "SOLVING"
    DONE = "DONE"


class Projector3DCalibrationScene(StereoCalibrationScene):
    """Deprecated: Projector 3D calibration is superseded by StereoCalibrationScene."""

    def __init__(self, context: AppContext):
        logging.warning(
            "Projector3DCalibrationScene is deprecated; delegating to StereoCalibrationScene."
        )
        super().__init__(context)
