from __future__ import annotations
import cv2
import numpy as np
import time
import os
import math
import mediapipe as mp
from typing import List, Tuple, Any, Dict

from light_map.common_types import (
    AppConfig,
    SceneId,
)
from light_map.renderer import Renderer
from light_map.gestures import detect_gesture
from light_map.map_system import MapSystem
from light_map.svg_loader import SVGLoader
from light_map.map_config import MapConfigManager
from light_map.session_manager import SessionManager
from light_map.display_utils import draw_dashed_circle

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
from light_map.token_tracker import TokenTracker
from light_map.common_types import TokenDetectionAlgorithm
from light_map.vision.token_filter import TokenFilter


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
        self.token_tracker = TokenTracker()
        self.token_filter = TokenFilter()

        # Load Camera Calibration
        camera_matrix = None
        dist_coeffs = None
        if os.path.exists("camera_calibration.npz"):
            calib = np.load("camera_calibration.npz")
            camera_matrix = calib["camera_matrix"]
            dist_coeffs = calib["dist_coeffs"]
            print("Loaded camera intrinsics.")

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # AppContext (shared state for scenes)
        self.app_context = AppContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            projector_matrix=self.config.projector_matrix,
            notifications=self.notifications,
            distortion_model=self.config.distortion_model,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
        )

        # Scene Management
        self.scenes: Dict[SceneId, Scene] = {
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
        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

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

        # We keep the map system and config manager to preserve state
        # But we need to update projector matrix in context and map system dims
        self.map_system.width = self.config.width
        self.map_system.height = self.config.height

        # Load Camera Calibration
        camera_matrix = None
        dist_coeffs = None
        if os.path.exists("camera_calibration.npz"):
            calib = np.load("camera_calibration.npz")
            camera_matrix = calib["camera_matrix"]
            dist_coeffs = calib["dist_coeffs"]

        self.app_context = AppContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            projector_matrix=self.config.projector_matrix,
            notifications=self.notifications,
            distortion_model=self.config.distortion_model,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            debug_mode=self.app_context.debug_mode,
            show_tokens=self.app_context.show_tokens,
        )

        # Re-initialize scenes with new context
        self.scenes = {
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
        # Reset to Menu or Viewing?
        # Ideally preserve current scene type if possible, but simple reset is safer.
        self.current_scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def _switch_scene(self, transition):
        target_id = transition.target_scene
        if target_id in self.scenes:
            self.current_scene.on_exit()
            self.current_scene = self.scenes[target_id]
            self.current_scene.on_enter(transition.payload)
        else:
            print(f"Error: Scene '{target_id}' not found.")

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
        inputs = self._convert_mediapipe_to_inputs(results, frame.shape)

        # 3. ArUco Background Tracking
        if self.map_config.get_detection_algorithm() == TokenDetectionAlgorithm.ARUCO:
            self._process_aruco_tracking(frame)

        # 4. Scene Update
        transition = self.current_scene.update(inputs, current_time)
        if transition:
            self._handle_payloads(transition.payload)
            self._switch_scene(transition)

        # 4. Base Render (Map Background)
        base_frame = self._render_base_layer(frame)

        # 5. Scene Render
        scene_frame = self.current_scene.render(base_frame)

        # 6. Global Overlays
        final_frame = self._render_global_overlays(scene_frame, inputs)

        return final_frame, []

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

    def _convert_mediapipe_to_inputs(
        self, results: Any, frame_shape: Tuple[int, int, int]
    ) -> List[HandInput]:
        """Converts raw MediaPipe results to a list of HandInput objects."""
        inputs = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return inputs

        matrix = self.config.projector_matrix.astype(np.float32)

        for i, landmarks in enumerate(results.multi_hand_landmarks):
            handedness = results.multi_handedness[i]
            gesture = detect_gesture(
                landmarks.landmark, handedness.classification[0].label
            )

            tip = landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
            cam_point = np.array(
                [tip.x * frame_shape[1], tip.y * frame_shape[0]], dtype=np.float32
            ).reshape(1, 1, 2)

            if self.app_context.distortion_model:
                proj_point = self.app_context.distortion_model.apply_correction(
                    cam_point
                )[0][0]
            else:
                proj_point = cv2.perspectiveTransform(cam_point, matrix)[0][0]

            inputs.append(
                HandInput(
                    gesture=gesture,
                    proj_pos=(int(proj_point[0]), int(proj_point[1])),
                    raw_landmarks=landmarks,
                )
            )
        return inputs

    def _handle_payloads(self, payload: Any):
        """Handle side-effects from scene transitions, like loading maps."""
        if isinstance(payload, dict) and "map_file" in payload:
            self.load_map(payload["map_file"], payload.get("load_session", False))

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        import os

        filename = os.path.abspath(filename)
        self.map_system.svg_loader = SVGLoader(filename)

        entry = self.map_config.data.maps.get(filename)
        if not entry or entry.grid_spacing_svg <= 0:
            # Auto-detection logic here if needed...
            pass

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
        # This handles the case where load_map is called during startup
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
                self._draw_ghost_tokens(frame)

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
            self._draw_debug_overlay(frame, inputs)

        # Notifications
        for i, msg in enumerate(self.notifications.get_active_notifications()):
            cv2.putText(
                frame,
                msg,
                (50, 100 + i * 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )

        return frame

    def _process_aruco_tracking(self, frame: np.ndarray):
        """Performs background ArUco tracking and updates the map system."""
        map_file = (
            self.map_system.svg_loader.filename if self.map_system.svg_loader else None
        )
        current_time = self.time_provider()

        # Get resolved configs for current map
        token_configs = self.map_config.get_aruco_configs(map_file)

        # Detect
        detections = self.token_tracker.detect_tokens(
            frame_white=frame,
            projector_matrix=self.config.projector_matrix,
            map_system=self.map_system,
            ppi=self.map_config.get_ppi(),
            algorithm=TokenDetectionAlgorithm.ARUCO,
            token_configs=token_configs,
            distortion_model=self.config.distortion_model,
        )

        # Grid parameters
        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        if map_file:
            entry = self.map_config.data.maps.get(map_file)
            if entry:
                grid_spacing = entry.grid_spacing_svg
                grid_origin_x = entry.grid_origin_svg_x
                grid_origin_y = entry.grid_origin_svg_y

        # Temporal Filtering and Grid Snapping
        tokens = self.token_filter.update(
            detections,
            current_time,
            grid_spacing=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            token_configs=token_configs,
        )

        # Update context
        self.map_system.ghost_tokens = tokens

    def _draw_ghost_tokens(self, image: np.ndarray):
        ppi = self.map_config.get_ppi()
        map_file = (
            self.map_system.svg_loader.filename if self.map_system.svg_loader else None
        )

        for t in self.map_system.ghost_tokens:
            sx, sy = self.map_system.world_to_screen(t.world_x, t.world_y)

            # Resolve properties for display
            resolved = self.map_config.resolve_token_profile(t.id, map_file)

            # Radius based on size (1 grid cell = 1 inch = ppi pixels)
            radius = int(ppi * resolved.size / 2) if ppi > 0 else 30

            # Draw circle
            color = (255, 255, 0)  # Cyan/Yellow
            if t.is_duplicate:
                color = (0, 0, 255)  # Red for duplicates
            elif not resolved.is_known:
                color = (200, 200, 200)  # Gray for unknown
            elif resolved.type == "PC":
                color = (0, 255, 0)  # Green for players
            elif resolved.type == "NPC":
                color = (0, 0, 255)  # Red for NPCs

            if t.is_occluded:
                # Pulse brightness
                pulse = (math.sin(self.time_provider() * 10) + 1) / 2
                alpha_pulse = 0.2 + 0.8 * pulse
                color = tuple(int(c * alpha_pulse) for c in color)

            if t.is_duplicate:
                draw_dashed_circle(image, (int(sx), int(sy)), radius, color, 2)
                cv2.putText(
                    image,
                    "DUPLICATE",
                    (int(sx) - radius, int(sy) + radius + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )
            elif not resolved.is_known:
                draw_dashed_circle(image, (int(sx), int(sy)), radius, color, 2)
                # Draw "?" in the center
                cv2.putText(
                    image,
                    "?",
                    (int(sx) - 8, int(sy) + 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color,
                    2,
                )
            else:
                cv2.circle(image, (int(sx), int(sy)), radius, color, 2)

            # Draw name
            cv2.putText(
                image,
                resolved.name,
                (int(sx) - radius, int(sy) - radius - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

    def _draw_debug_overlay(self, image, inputs: List[HandInput]):
        cv2.putText(
            image,
            f"FPS: {int(self.fps)} | Scene: {self.current_scene.__class__.__name__}",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
        for hand_input in inputs:
            px, py = hand_input.proj_pos
            label = hand_input.gesture.name
            cv2.putText(
                image,
                label,
                (px, py - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
            cv2.circle(image, (px, py), 10, (0, 255, 255), -1)
