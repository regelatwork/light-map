from __future__ import annotations
import cv2
import numpy as np
import time
import os
import logging
from typing import List, Tuple, Any, Dict, Optional

from light_map.common_types import (
    AppConfig,
    SceneId,
)
from light_map.renderer import Renderer
from light_map.map_system import MapSystem
from light_map.svg_loader import SVGLoader
from light_map.map_config import MapConfigManager
from light_map.session_manager import SessionManager

from light_map.core.app_context import AppContext
from light_map.core.notification import NotificationManager
from light_map.core.scene import Scene, HandInput
from light_map.scenes.menu_scene import MenuScene
from light_map.scenes.map_scene import MapScene, ViewingScene
from light_map.scenes.scanning_scene import ScanningScene
from light_map.scenes.calibration_scenes import (
    FlashCalibrationScene,
    MapGridCalibrationScene,
    PpiCalibrationScene,
    IntrinsicsCalibrationScene,
    ProjectorCalibrationScene,
    ExtrinsicsCalibrationScene,
)


from light_map.vision.tracking_coordinator import TrackingCoordinator
from light_map.vision.input_processor import InputProcessor
from light_map.vision.overlay_renderer import OverlayRenderer
from light_map.vision.hand_masker import HandMasker


class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider
        self.last_fps_time = 0.0
        self.fps = 0.0

        # Core Systems
        self.renderer = Renderer(config.width, config.height)
        self.map_system = MapSystem(config.width, config.height)
        self.map_config = MapConfigManager()
        self.notifications = NotificationManager()

        # New Modular Coordinators
        self.tracking_coordinator = TrackingCoordinator(time_provider)
        self.input_processor = InputProcessor(config)
        self.hand_masker = HandMasker()

        # Load Camera Calibration
        camera_matrix, dist_coeffs = self._load_camera_calibration()

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # AppContext (shared state for scenes)
        self.app_context = self._create_app_context(camera_matrix, dist_coeffs)
        self.overlay_renderer = OverlayRenderer(self.app_context)

        # Scene Management
        self.scenes = self._initialize_scenes()
        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def _load_camera_calibration(
        self,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if os.path.exists("camera_calibration.npz"):
            calib = np.load("camera_calibration.npz")
            logging.info("Loaded camera intrinsics.")
            return calib["camera_matrix"], calib["dist_coeffs"]
        return None, None

    def _create_app_context(
        self, camera_matrix, dist_coeffs, debug_mode=False, show_tokens=True
    ) -> AppContext:
        return AppContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            projector_matrix=self.config.projector_matrix,
            notifications=self.notifications,
            distortion_model=self.config.distortion_model,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            debug_mode=debug_mode,
            show_tokens=show_tokens,
        )

    def _initialize_scenes(self) -> Dict[SceneId, Scene]:
        return {
            SceneId.MENU: MenuScene(self.app_context),
            SceneId.VIEWING: ViewingScene(self.app_context),
            SceneId.MAP: MapScene(self.app_context),
            SceneId.SCANNING: ScanningScene(self.app_context),
            SceneId.CALIBRATE_FLASH: FlashCalibrationScene(self.app_context),
            SceneId.CALIBRATE_PPI: PpiCalibrationScene(self.app_context),
            SceneId.CALIBRATE_MAP_GRID: MapGridCalibrationScene(self.app_context),
            SceneId.CALIBRATE_INTRINSICS: IntrinsicsCalibrationScene(self.app_context),
            SceneId.CALIBRATE_PROJECTOR: ProjectorCalibrationScene(self.app_context),
            SceneId.CALIBRATE_EXTRINSICS: ExtrinsicsCalibrationScene(self.app_context),
        }

    @property
    def debug_mode(self) -> bool:
        return self.app_context.debug_mode

    @debug_mode.setter
    def debug_mode(self, enabled: bool):
        self.app_context.debug_mode = enabled

    def set_debug_mode(self, enabled: bool):
        self.app_context.debug_mode = enabled

    def reload_config(self, new_config: AppConfig):
        """Reloads application configuration, rebuilding context and scenes."""
        self.config = new_config
        self.renderer = Renderer(new_config.width, new_config.height)
        self.input_processor = InputProcessor(new_config)

        # We keep the map system and config manager to preserve state
        self.map_system.width = self.config.width
        self.map_system.height = self.config.height

        camera_matrix, dist_coeffs = self._load_camera_calibration()

        self.app_context = self._create_app_context(
            camera_matrix,
            dist_coeffs,
            debug_mode=self.app_context.debug_mode,
            show_tokens=self.app_context.show_tokens,
        )
        self.overlay_renderer = OverlayRenderer(self.app_context)

        # Re-initialize scenes with new context
        self.scenes = self._initialize_scenes()
        self.current_scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def _switch_scene(self, transition):
        target_id = transition.target_scene
        if target_id in self.scenes:
            self.current_scene.on_exit()
            self.current_scene = self.scenes[target_id]
            self.current_scene.on_enter(transition.payload)
        else:
            logging.error("Scene '%s' not found.", target_id)

    def process_frame(
        self, frame: np.ndarray, results: Any
    ) -> Tuple[np.ndarray, List[str]]:
        self.app_context.last_camera_frame = frame
        current_time = self.time_provider()

        # 1. Update FPS
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # 2. Standardize Input
        inputs = self.input_processor.convert_mediapipe_to_inputs(results, frame.shape)

        # 3. ArUco Background Tracking
        self.tracking_coordinator.process_aruco_tracking(
            frame, self.config, self.map_system, self.map_config
        )

        # 4. Scene Update
        transition = self.current_scene.update(inputs, current_time)
        if transition:
            self._handle_payloads(transition.payload)
            self._switch_scene(transition)

        # 4. Base Render (Map Background)
        base_frame = self._render_base_layer(frame)

        # 5. Scene Render
        scene_frame = self.current_scene.render(base_frame)

        # 6. Hand Masking (Digital Shadow)
        masked_frame = self._apply_hand_masking(scene_frame, results)

        # 7. Global Overlays
        final_frame = self._render_global_overlays(masked_frame, inputs)

        return final_frame, []

    def _apply_hand_masking(self, frame: np.ndarray, results: Any) -> np.ndarray:
        if not self.config.enable_hand_masking:
            return frame

        if not results or not results.multi_hand_landmarks:
            # Still call compute_hulls with empty list for persistence
            hulls = self.hand_masker.compute_hulls([], None)
        else:

            def transform_pts(pts):
                # pts is (N, 2) normalized
                cam_pts = pts.reshape(-1, 1, 2).copy()
                cam_pts[:, :, 0] *= self.app_context.last_camera_frame.shape[1]
                cam_pts[:, :, 1] *= self.app_context.last_camera_frame.shape[0]

                if self.config.distortion_model:
                    proj_pts = self.config.distortion_model.apply_correction(cam_pts)
                else:
                    proj_pts = cv2.perspectiveTransform(
                        cam_pts, self.config.projector_matrix
                    )
                return proj_pts.reshape(-1, 2)

            hulls = self.hand_masker.compute_hulls(
                results.multi_hand_landmarks, transform_pts
            )

        if hulls:
            mask = self.hand_masker.generate_mask_image(
                hulls,
                self.config.width,
                self.config.height,
                padding=self.config.hand_mask_padding,
                blur=self.config.hand_mask_blur,
            )
            # Apply mask
            frame[mask > 127] = 0

        return frame

    def _render_base_layer(self, frame: np.ndarray) -> np.ndarray:
        """Renders the map background if applicable, or returns a blank frame."""
        if self.map_system.is_map_loaded() and not isinstance(
            self.current_scene, MenuScene
        ):
            is_interacting = (
                getattr(self.current_scene, "is_interacting", False)
                if self.current_scene
                else False
            )
            quality = 0.25 if is_interacting else 1.0
            map_image = self.map_system.svg_loader.render(
                self.config.width,
                self.config.height,
                quality=quality,
                **self.map_system.get_render_params(),
            )
            map_opacity = 0.5 if is_interacting else 1.0

            if map_opacity < 1.0:
                return cv2.convertScaleAbs(map_image, alpha=map_opacity, beta=0)
            return map_image.copy()

        return np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)

    def _handle_payloads(self, payload: Any):
        """Handle side-effects from scene transitions, like loading maps."""
        if isinstance(payload, dict) and "map_file" in payload:
            self.load_map(payload["map_file"], payload.get("load_session", False))

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        filename = os.path.abspath(filename)
        self.map_system.svg_loader = SVGLoader(filename)

        entry = self.map_config.data.maps.get(filename)

        if load_session:
            session = SessionManager.load_for_map(filename)
            if session:
                self.map_system.ghost_tokens = session.tokens
                if session.viewport:
                    self.map_system.set_state(
                        session.viewport.x,
                        session.viewport.y,
                        session.viewport.zoom,
                        session.viewport.rotation,
                    )
                self.map_config.data.global_settings.last_used_map = filename
                self.map_config.save()
                return

        # Default loading if no session or session load failed
        vp = self.map_config.get_map_viewport(filename)
        self.map_system.set_state(vp.x, vp.y, vp.zoom, vp.rotation)
        self.map_system.base_scale = (
            entry.scale_factor_1to1 if entry and entry.scale_factor_1to1 > 0 else 1.0
        )
        self.map_config.data.global_settings.last_used_map = filename
        self.map_config.save()

        # Switch to Viewing Scene to ensure map is visible
        if SceneId.VIEWING in self.scenes:
            target_scene = self.scenes[SceneId.VIEWING]
            if self.current_scene != target_scene:
                self.current_scene.on_exit()
                self.current_scene = target_scene
                self.current_scene.on_enter()

    def _render_global_overlays(
        self, frame: np.ndarray, inputs: List[HandInput]
    ) -> np.ndarray:
        """Renders UI elements that are always visible, like debug info and notifications."""

        # Check if the current scene requests to hide overlays (e.g. during scanning)
        if getattr(self.current_scene, "should_hide_overlays", False):
            return frame

        # Draw Ghost Tokens
        should_show_tokens = isinstance(self.current_scene, (ViewingScene, MapScene))

        if should_show_tokens and self.map_system.ghost_tokens:
            if self.app_context.show_tokens:
                self.overlay_renderer.draw_ghost_tokens(frame, self.time_provider)

            # Draw Token Count
            count = len(self.map_system.ghost_tokens)
            status = "" if self.app_context.show_tokens else " (Hidden)"
            cv2.putText(
                frame,
                f"Tokens: {count}{status}",
                (50, self.config.height - 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

        # Debug Overlay
        if self.app_context.debug_mode:
            self.overlay_renderer.draw_debug_overlay(
                frame, self.fps, self.current_scene.__class__.__name__, inputs
            )

        return frame

    def _draw_ghost_tokens(self, image: np.ndarray):
        """Delegate to OverlayRenderer for test compatibility."""
        self.overlay_renderer.draw_ghost_tokens(image, self.time_provider)

    def _draw_debug_overlay(self, image: np.ndarray, inputs: List[HandInput]):
        """Delegate to OverlayRenderer for test compatibility."""
        self.overlay_renderer.draw_debug_overlay(
            image, self.fps, self.current_scene.__class__.__name__, inputs
        )
