from __future__ import annotations
import cv2
import numpy as np
import time
import os
import sys
import logging
from typing import List, Tuple, Any, Dict, Optional, TYPE_CHECKING, Callable

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
from light_map.core.analytics import AnalyticsManager
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
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.display_utils import draw_text_with_background

if TYPE_CHECKING:
    from light_map.core.world_state import WorldState
    from light_map.common_types import Action, Token


class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider
        self.last_fps_time = 0.0
        self.fps = 0.0

        # Core Systems
        self.renderer = Renderer(config.width, config.height)
        self.map_system = MapSystem(config.width, config.height)
        self.map_config = MapConfigManager(storage=config.storage_manager)
        self.notifications = NotificationManager()

        # New Modular Coordinators
        self.tracking_coordinator = TrackingCoordinator(time_provider)
        self.input_processor = InputProcessor(config)
        self.hand_masker = HandMasker()

        # Load Camera Calibration
        camera_matrix, dist_coeffs, rvec, tvec = self._load_camera_calibration()

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # AppContext (shared state for scenes)
        self.app_context = self._create_app_context(
            camera_matrix, dist_coeffs, rvec, tvec
        )
        self.overlay_renderer = OverlayRenderer(self.app_context)

        # Scene Management
        self.scenes = self._initialize_scenes()
        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

        # Map Rendering Cache
        self._cached_map_image: Optional[np.ndarray] = None
        self._last_render_params: Dict[str, Any] = {}

    def _load_camera_calibration(
        self,
    ) -> Tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        camera_matrix = None
        dist_coeffs = None
        rvec = None
        tvec = None

        storage = self.config.storage_manager
        intrinsics_path = (
            storage.get_data_path("camera_calibration.npz")
            if storage
            else "camera_calibration.npz"
        )
        extrinsics_path = (
            storage.get_data_path("camera_extrinsics.npz")
            if storage
            else "camera_extrinsics.npz"
        )

        missing = []
        if not os.path.exists(intrinsics_path):
            missing.append(intrinsics_path)
        if not os.path.exists(extrinsics_path):
            missing.append(extrinsics_path)

        if missing:
            msg = (
                "\n" + "!" * 60 + "\n"
                "CRITICAL ERROR: Camera Calibration Files Missing!\n"
                f"  Missing files: {', '.join(missing)}\n"
                "  The system cannot map tokens without camera calibration.\n"
                "  PLEASE RUN: python3 projector_calibration.py\n"
                "!" * 60 + "\n"
            )
            logging.critical(msg)
            sys.exit(1)

        try:
            calib = np.load(intrinsics_path)
            camera_matrix = calib["camera_matrix"]
            dist_coeffs = calib["dist_coeffs"]
            logging.info("Loaded camera intrinsics from %s.", intrinsics_path)

            ext = np.load(extrinsics_path)
            rvec = ext["rvec"]
            tvec = ext["tvec"]
            logging.info("Loaded camera extrinsics from %s.", extrinsics_path)
        except Exception as e:
            logging.critical("Failed to load calibration data: %s", e)
            sys.exit(1)

        return camera_matrix, dist_coeffs, rvec, tvec

    def _create_app_context(
        self,
        camera_matrix,
        dist_coeffs,
        rvec=None,
        tvec=None,
        debug_mode=False,
        show_tokens=True,
    ) -> AppContext:
        storage = self.config.storage_manager
        intrinsics_path = (
            storage.get_data_path("camera_calibration.npz")
            if storage
            else None
        )
        extrinsics_path = (
            storage.get_data_path("camera_extrinsics.npz")
            if storage
            else None
        )

        aruco_detector = ArucoTokenDetector(
            calibration_file=intrinsics_path,
            extrinsics_file=extrinsics_path
        )
        # Fallback if for some reason they weren't loaded in constructor
        # (though our check above makes this unlikely to be None if we reached here)
        if aruco_detector.camera_matrix is None and camera_matrix is not None:
            aruco_detector.set_calibration(camera_matrix, dist_coeffs)
        if aruco_detector.rvec is None and rvec is not None:
            aruco_detector.set_extrinsics(rvec, tvec)

        return AppContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            projector_matrix=self.config.projector_matrix,
            notifications=self.notifications,
            distortion_model=self.config.distortion_model,
            aruco_detector=aruco_detector,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            camera_rvec=rvec,
            camera_tvec=tvec,
            debug_mode=debug_mode,
            show_tokens=show_tokens,
            analytics=AnalyticsManager(self.config.storage_manager),
        )

    @property
    def aruco_mapper(self) -> Optional[Callable[[Dict[str, Any]], List[Token]]]:
        """Provides a mapping function for the MainLoopController."""
        if not self.app_context.aruco_detector:
            return None

        def mapper(raw_data):
            return self.app_context.aruco_detector.map_to_tokens(
                raw_data,
                self.map_system,
                token_configs=self.map_config.get_aruco_configs(
                    self.map_system.svg_loader.filename
                    if self.map_system.svg_loader
                    else None
                ),
                ppi=self.map_config.get_ppi(),
                distortion_model=self.config.distortion_model,
            )

        return mapper

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

        camera_matrix, dist_coeffs, rvec, tvec = self._load_camera_calibration()

        self.app_context = self._create_app_context(
            camera_matrix,
            dist_coeffs,
            rvec,
            tvec,
            debug_mode=self.app_context.debug_mode,
            show_tokens=self.app_context.show_tokens,
        )
        self.overlay_renderer = OverlayRenderer(self.app_context)

        # Reset map cache
        self._cached_map_image = None
        self._last_render_params = {}

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

    def process_state(
        self, state: "WorldState", actions: List["Action"]
    ) -> Tuple[np.ndarray, List[str]]:
        current_time = self.time_provider()

        # Update FPS
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # Update context frame if available
        if state.background is not None:
            self.app_context.last_camera_frame = state.background
            frame_shape = state.background.shape
        else:
            frame_shape = (self.config.height, self.config.width, 3)

        # Build dummy results for legacy processors, or update processors
        class DummyResults:
            def __init__(self, hands_list, handedness_list):
                self.multi_hand_landmarks = []
                self.multi_handedness = []

                for hl in hands_list:

                    class DummyHandLandmarks:
                        def __init__(self, lm_dicts):
                            class DummyLandmark:
                                def __init__(self, d):
                                    self.x = d.get("x", 0)
                                    self.y = d.get("y", 0)
                                    self.z = d.get("z", 0)

                            self.landmark = [DummyLandmark(d) for d in lm_dicts]

                    self.multi_hand_landmarks.append(DummyHandLandmarks(hl))

                for h in handedness_list:

                    class DummyHandedness:
                        def __init__(self, h_dict):
                            class DummyClassification:
                                def __init__(self, d):
                                    self.label = d.get("label", "Left")
                                    self.score = d.get("score", 1.0)

                            self.classification = [DummyClassification(h_dict)]

                    self.multi_handedness.append(DummyHandedness(h))

        results = DummyResults(state.hands, state.handedness)

        # Update app context with latest vision results
        self.app_context.last_camera_frame = state.background
        self.app_context.raw_aruco = state.raw_aruco

        # Standardize Input
        inputs = self.input_processor.convert_mediapipe_to_inputs(results, frame_shape)

        # Map actions to inputs if needed? We will just pass the mapped inputs for now
        # You could also blend `actions` into `inputs` if your scene requires Action enums

        # We need to update tokens in map system from state
        if state.tokens:
            self.map_system.ghost_tokens = state.tokens

        # Scene Update
        transition = self.current_scene.update(inputs, current_time)
        if transition:
            self._handle_payloads(transition.payload)
            self._switch_scene(transition)

        t_start = time.perf_counter_ns()
        # Render Base Layer
        if state.background is not None:
            base_frame = self._render_base_layer(state.background)
        else:
            base_frame = np.zeros(frame_shape, dtype=np.uint8)
        t_base = time.perf_counter_ns()

        # Scene Render
        # We MUST pass a copy because the scenes might draw directly onto the frame,
        # and we don't want to pollute the cached base layer.
        scene_frame = self.current_scene.render(base_frame.copy())
        t_scene = time.perf_counter_ns()

        # Hand Masking
        masked_frame = self._apply_hand_masking(scene_frame, results)
        t_mask = time.perf_counter_ns()

        # Global Overlays
        final_frame = self._render_global_overlays(masked_frame, inputs)
        t_overlays = time.perf_counter_ns()

        # Log breakdown if total exceeds threshold (e.g., 50ms)
        total_ms = (t_overlays - t_start) / 1_000_000.0
        if total_ms > 50.0:
            logging.info(
                f"RENDER BREAKDOWN ({total_ms:.1f}ms): "
                f"base={(t_base - t_start) / 1_000_000.0:.1f}ms, "
                f"scene={(t_scene - t_base) / 1_000_000.0:.1f}ms, "
                f"mask={(t_mask - t_scene) / 1_000_000.0:.1f}ms, "
                f"overlays={(t_overlays - t_mask) / 1_000_000.0:.1f}ms"
            )

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
            _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY_INV)
            frame = cv2.bitwise_and(frame, frame, mask=binary_mask)

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
            params = self.map_system.get_render_params()
            params["quality"] = quality

            # Check if we can reuse the cached map image
            if (
                self._cached_map_image is not None
                and params == self._last_render_params
            ):
                map_image = self._cached_map_image
            else:
                # Cache miss: render and store
                logging.info(
                    f"Map Cache Miss! New params: {params}, Old params: {self._last_render_params}"
                )
                map_image = self.map_system.svg_loader.render(
                    self.config.width,
                    self.config.height,
                    quality=quality,
                    **self.map_system.get_render_params(),
                )
                self._cached_map_image = map_image
                self._last_render_params = params.copy()

            map_opacity = 0.5 if is_interacting else 1.0

            if map_opacity >= 1.0:
                return map_image
            return cv2.convertScaleAbs(map_image, alpha=map_opacity, beta=0)

        return np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)

    def _handle_payloads(self, payload: Any):
        """Handle side-effects from scene transitions, like loading maps."""
        if isinstance(payload, dict) and "map_file" in payload:
            self.load_map(payload["map_file"], payload.get("load_session", False))

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        filename = os.path.abspath(filename)
        self.map_system.svg_loader = SVGLoader(filename)

        # Reset map cache
        self._cached_map_image = None
        self._last_render_params = {}

        entry = self.map_config.data.maps.get(filename)

        if load_session:
            session_dir = None
            if self.config.storage_manager:
                session_dir = os.path.join(
                    self.config.storage_manager.get_data_dir(), "sessions"
                )
            session = SessionManager.load_for_map(filename, session_dir=session_dir)
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

    def save_session(self):
        """Saves the current session (tokens and viewport)."""
        if not self.map_system.is_map_loaded():
            return

        map_file = self.map_system.svg_loader.filename
        session_dir = None
        if self.config.storage_manager:
            session_dir = os.path.join(
                self.config.storage_manager.get_data_dir(), "sessions"
            )

        from light_map.common_types import SessionData, ViewportState

        session = SessionData(
            map_file=map_file,
            viewport=ViewportState(
                x=self.map_system.state.x,
                y=self.map_system.state.y,
                zoom=self.map_system.state.zoom,
                rotation=self.map_system.state.rotation,
            ),
            tokens=self.map_system.ghost_tokens,
        )
        SessionManager.save_for_map(map_file, session, session_dir=session_dir)

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
            draw_text_with_background(
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

        # Draw notifications
        self.overlay_renderer.draw_notifications(frame)

        return frame

    def _draw_ghost_tokens(self, image: np.ndarray):
        """Delegate to OverlayRenderer for test compatibility."""
        self.overlay_renderer.draw_ghost_tokens(image, self.time_provider)

    def _draw_debug_overlay(self, image: np.ndarray, inputs: List[HandInput]):
        """Delegate to OverlayRenderer for test compatibility."""
        self.overlay_renderer.draw_debug_overlay(
            image, self.fps, self.current_scene.__class__.__name__, inputs
        )
