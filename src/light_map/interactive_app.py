from __future__ import annotations
import numpy as np
import cv2
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
from light_map.map_layer import MapLayer
from light_map.menu_layer import MenuLayer
from light_map.scene_layer import SceneLayer
from light_map.hand_mask_layer import HandMaskLayer
from light_map.overlay_layer import TokenLayer, NotificationLayer, DebugLayer
from light_map.map_system import MapSystem
from light_map.svg_loader import SVGLoader
from light_map.map_config import MapConfigManager
from light_map.session_manager import SessionManager
from light_map.fow_manager import FogOfWarManager
from light_map.fow_layer import FogOfWarLayer
from light_map.visibility_layer import VisibilityLayer
from light_map.visibility_engine import VisibilityEngine
from light_map.cursor_layer import CursorLayer

from light_map.core.app_context import AppContext
from light_map.core.analytics import AnalyticsManager
from light_map.core.notification import NotificationManager
from light_map.core.scene import Scene
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
from light_map.vision.input_processor import InputProcessor, DummyResults
from light_map.vision.aruco_detector import ArucoTokenDetector

from light_map.core.world_state import WorldState

if TYPE_CHECKING:
    from light_map.common_types import Action, Token


class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider
        self.last_fps_time = 0.0
        self.fps = 0.0

        # State management
        self.state = WorldState()

        # Core Systems
        self.renderer = Renderer(config.width, config.height)
        self.map_system = MapSystem(config.width, config.height)
        self.map_config = MapConfigManager(storage=config.storage_manager)
        self.notifications = NotificationManager()

        # Visibility and FoW Systems
        # Use a temporary engine until map is loaded
        self.visibility_engine = VisibilityEngine(grid_spacing_svg=10.0)
        self.fow_manager = FogOfWarManager(config.width, config.height)
        self.fow_layer = FogOfWarLayer(self.fow_manager)
        self.visibility_layer = VisibilityLayer(self.state, config.width, config.height)
        self.inspected_token_id: Optional[int] = None

        # New Modular Coordinators
        self.tracking_coordinator = TrackingCoordinator(time_provider)
        self.input_processor = InputProcessor(config)

        # Performance Tracking
        from .core.analytics import LatencyInstrument

        self.instrument = LatencyInstrument()

        # Load Camera Calibration
        camera_matrix, dist_coeffs, rvec, tvec = self._load_camera_calibration()

        # Normalize calibration if resolution mismatch
        camera_matrix, rvec, tvec = self._normalize_calibration(
            camera_matrix, rvec, tvec
        )

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # AppContext (shared state for scenes)
        # Sync calibration to background tracker
        self.tracking_coordinator.token_tracker.set_aruco_calibration(
            camera_matrix, dist_coeffs, rvec, tvec
        )

        self.app_context = self._create_app_context(
            camera_matrix, dist_coeffs, rvec, tvec
        )

        # Initialize Layers
        self.map_layer = MapLayer(
            self.state, self.map_system, config.width, config.height
        )
        self.scene_layer = SceneLayer(
            self.state, None, config.width, config.height, is_static=False
        )
        self.hand_mask_layer = HandMaskLayer(self.state, config)
        self.menu_layer = MenuLayer(self.state)
        self.token_layer = TokenLayer(self.state, self.app_context)
        self.notification_layer = NotificationLayer(self.state, self.app_context)
        self.debug_layer = DebugLayer(self.state, self.app_context)
        self.cursor_layer = CursorLayer(self.state, self.app_context)

        # Layer Stack (Bottom to Top)
        self.layer_stack = [
            self.map_layer,
            self.fow_layer,
            self.visibility_layer,
            self.scene_layer,
            self.hand_mask_layer,
            self.menu_layer,
            self.token_layer,
            self.notification_layer,
            self.debug_layer,
            self.cursor_layer,
        ]

        # Scene Management
        self.scenes = self._initialize_scenes()
        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def _normalize_calibration(
        self, camera_matrix: np.ndarray, rvec: np.ndarray, tvec: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Normalizes camera_matrix and projector_matrix if the current camera resolution
        differs from the resolution used during calibration.
        """
        cam_w, cam_h = self.config.camera_resolution
        calib_w, calib_h = self.config.projector_matrix_resolution

        if cam_w == 0 or calib_w == 0:
            return camera_matrix, rvec, tvec

        if cam_w == calib_w and cam_h == calib_h:
            return camera_matrix, rvec, tvec

        logging.info(
            f"InteractiveApp: Normalizing calibration from {calib_w}x{calib_h} to {cam_w}x{cam_h}"
        )

        # 1. Normalize Camera Intrinsics
        # K_new = K_old * diag(W_new/W_old, H_new/H_old, 1)
        scale_x = cam_w / calib_w
        scale_y = cam_h / calib_h

        new_camera_matrix = camera_matrix.copy()
        new_camera_matrix[0, 0] *= scale_x  # fx
        new_camera_matrix[0, 2] *= scale_x  # cx
        new_camera_matrix[1, 1] *= scale_y  # fy
        new_camera_matrix[1, 2] *= scale_y  # cy

        # 2. Normalize Projector Homography (Camera -> Projector)
        # H_runtime = H_calib * S
        # S maps runtime (W_new, H_new) to calibration (W_old, H_old)
        # S = diag(W_old/W_new, H_old/H_new, 1)
        inv_scale_x = calib_w / cam_w
        inv_scale_y = calib_h / cam_h

        S = np.array(
            [[inv_scale_x, 0, 0], [0, inv_scale_y, 0], [0, 0, 1]], dtype=np.float32
        )

        self.config.projector_matrix = self.config.projector_matrix @ S

        return new_camera_matrix, rvec, tvec

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
            storage.get_data_path("camera_calibration.npz") if storage else None
        )
        extrinsics_path = (
            storage.get_data_path("camera_extrinsics.npz") if storage else None
        )

        aruco_detector = ArucoTokenDetector(
            calibration_file=intrinsics_path, extrinsics_file=extrinsics_path
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
            res = self.tracking_coordinator.map_and_filter_aruco(
                raw_data,
                self.map_system,
                self.map_config,
                self.config,
            )
            if res.get("tokens"):
                logging.debug(f"aruco_mapper: Mapped {len(res['tokens'])} tokens.")
            return res

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

    @property
    def effective_show_tokens(self) -> bool:
        """Returns True if tokens should be shown (global setting AND scene preference)."""
        return self.app_context.show_tokens and getattr(
            self.current_scene, "show_tokens", True
        )

    @debug_mode.setter
    def debug_mode(self, enabled: bool):
        self.app_context.debug_mode = enabled

    def set_debug_mode(self, enabled: bool):
        if self.app_context.debug_mode != enabled:
            self.app_context.debug_mode = enabled
            self.state.notifications_timestamp += 1
        # Always ensure it is set correctly
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

        # Sync calibration to background tracker
        self.tracking_coordinator.token_tracker.set_aruco_calibration(
            camera_matrix, dist_coeffs, rvec, tvec
        )

        self.app_context = self._create_app_context(
            camera_matrix,
            dist_coeffs,
            rvec,
            tvec,
            debug_mode=self.app_context.debug_mode,
            show_tokens=self.app_context.show_tokens,
        )

        # Re-initialize scenes with new context
        self.scenes = self._initialize_scenes()
        self.current_scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def _switch_scene(self, transition):
        target_id = transition.target_scene
        if target_id in self.scenes:
            logging.debug("Switching scene to: %s", target_id)
            self.current_scene.on_exit()
            self.current_scene = self.scenes[target_id]
            self.current_scene.on_enter(transition.payload)
            self.state.increment_scene_timestamp()
        else:
            logging.error("Scene '%s' not found.", target_id)

    def process_state(
        self, state: Optional["WorldState"] = None, actions: List["Action"] = None
    ) -> Tuple[Optional[np.ndarray], List[str]]:
        from .core.analytics import track_wait

        # Log performance stats every 10s at DEBUG level
        self.instrument.log_and_reset_if_needed(interval_s=10.0, level=logging.DEBUG)

        if state is None:
            state = self.state
        if actions is None:
            actions = []

        # Ensure layers are using the passed state if it's different
        if state is not self.state:
            self.state = state
            for layer in self.layer_stack:
                layer.state = state

        current_time = self.time_provider()

        # Update FPS
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # Update WorldState with latest metrics
        state.fps = self.fps
        self.current_scene_name = self.current_scene.__class__.__name__
        state.current_scene_name = self.current_scene_name
        state.effective_show_tokens = self.effective_show_tokens
        state.update_viewport(self.map_system.state.to_viewport())

        # Update context frame if available
        if state.background is not None:
            self.app_context.last_camera_frame = state.background
            frame_shape = state.background.shape
        else:
            frame_shape = (self.config.height, self.config.width, 3)

        # Standardize Input
        # Priority 1: Raw landmarks from physical camera
        if state.hands or state.handedness:
            results = DummyResults(state.hands, state.handedness)
            inputs = self.input_processor.convert_mediapipe_to_inputs(
                results, frame_shape
            )
            state.update_inputs(inputs, current_time)
        # Priority 2: Use existing inputs (might be from Remote Driver)
        else:
            inputs = state.inputs
            # If we are in 'ignore' or 'merge' remote mode, and physical lost hand,
            # we should ensure inputs is cleared if it was a physical hand.
            # TrackingCoordinator/VisionProcessManager already handles this split
            # by either sending HandInput objects or Landmarks.
            if self.config.storage_manager:  # check if we are in a real app context
                # For now, let's trust state.inputs is the source of truth if hands is empty.
                pass

            # BUG-FIX: Expire inputs if no update received for > 200ms
            if inputs and (current_time - state.last_hand_timestamp > 0.2):
                logging.debug("Expiring hand inputs after 200ms of inactivity.")
                state.inputs = []
                state.hands_timestamp += 1
                inputs = []

        # Update app context with latest vision results
        self.app_context.last_camera_frame = state.background
        self.app_context.raw_aruco = state.raw_aruco
        self.app_context.raw_tokens = state.raw_tokens

        # --- VISIBILITY CALCULATION ---
        combined_pc_mask = None
        current_stack = self.current_scene.get_active_layers(self)

        if self.map_system.is_map_loaded():
            mask_w, mask_h = self.fow_manager.width, self.fow_manager.height

            # Aggregate LOS for all PC tokens
            pc_tokens = [
                t
                for t in state.tokens
                if self.map_config.resolve_token_profile(t.id).type == "PC"
            ]

            for token in pc_tokens:
                token_mask = self.visibility_engine.get_token_vision_mask(
                    token.id,
                    token.world_x,
                    token.world_y,
                    size=self.map_config.resolve_token_profile(token.id).size,
                    vision_range_grid=25.0,  # Default per design
                    mask_width=mask_w,
                    mask_height=mask_h,
                )
                if combined_pc_mask is None:
                    combined_pc_mask = token_mask.copy()
                else:
                    cv2.bitwise_or(combined_pc_mask, token_mask, combined_pc_mask)

            if combined_pc_mask is not None:
                self.fow_manager.set_visible_mask(combined_pc_mask)
                self.fow_layer.is_dirty = True
                state.update_visibility_mask(combined_pc_mask)

                # Check for "Exclusive Vision" (Token Inspection)
                # This state is expected to be set by scenes/inputs later.
                if self.inspected_token_id is not None:
                    # Find inspected token's mask
                    insp_token = next(
                        (t for t in state.tokens if t.id == self.inspected_token_id),
                        None,
                    )
                    if insp_token:
                        insp_mask = self.visibility_engine.get_token_vision_mask(
                            insp_token.id,
                            insp_token.world_x,
                            insp_token.world_y,
                            size=self.map_config.resolve_token_profile(
                                insp_token.id
                            ).size,
                            vision_range_grid=25.0,
                            mask_width=mask_w,
                            mask_height=mask_h,
                        )
                        # Switch to Exclusive Stack: Visibility (Full LOS) + Scene + Hand + Menu
                        current_stack = [
                            self.visibility_layer,
                            self.scene_layer,
                            self.hand_mask_layer,
                            self.menu_layer,
                        ]
                        # The visibility layer should be the single token's vision
                        state.update_visibility_mask(insp_mask)

        # We need to update tokens in map system from state
        self.map_system.ghost_tokens = state.tokens

        # Scene Update
        transition = self.current_scene.update(inputs, current_time)
        if transition:
            self._handle_payloads(transition.payload)
            self._switch_scene(transition)

        # Sync Menu State to WorldState

        menu_state = getattr(self.current_scene, "menu_state", None)
        state.update_menu_state(menu_state)

        # --- LAYERED RENDERING ---
        with track_wait("total_render_logic", self.instrument):
            t_start = time.perf_counter_ns()

            # 1. Update MapLayer params based on scene
            self.map_layer.opacity = 1.0
            is_interacting = getattr(self.current_scene, "is_interacting", False)
            self.map_layer.quality = 0.25 if is_interacting else 1.0

            # 2. Update SceneLayer bridge
            self.scene_layer.scene = self.current_scene
            # Only increment scene timestamp if scene is actually dirty
            if self.current_scene.is_dirty:
                state.increment_scene_timestamp()
                # Most scenes (especially legacy) draw every frame once rendered
                # or managing their own dirty flag.
                # We clear it here if it's a scene that doesn't draw itself.
                if not getattr(self.current_scene, "is_dynamic", False):
                    self.current_scene.is_dirty = False

            # 3. Perform Composite Render
            with track_wait("renderer_composite", self.instrument):
                final_frame = self.renderer.render(
                    state, current_stack, current_time, self.instrument
                )

            if final_frame is not None:
                total_ms = (time.perf_counter_ns() - t_start) / 1_000_000.0
                if total_ms > 50.0:
                    logging.debug(f"RENDER TOTAL: {total_ms:.1f}ms (Layered)")

        return final_frame, []

    def _handle_payloads(self, payload: Any):
        """Handle side-effects from scene transitions, like loading maps."""
        if not isinstance(payload, dict):
            return

        if "map_file" in payload:
            self.load_map(payload["map_file"], payload.get("load_session", False))

        if payload.get("action") == "SYNC_VISION":
            if self.fow_manager:
                self.fow_manager.reveal_area(self.fow_manager.visible_mask)
                self.fow_manager.save()
                self.fow_layer.is_dirty = True
                self.notifications.add_notification("Vision Synchronized")

        if payload.get("action") == "RESET_FOW":
            if self.fow_manager:
                self.fow_manager.reset()
                self.fow_manager.save()
                self.fow_layer.is_dirty = True
                self.notifications.add_notification("Fog of War Reset")

        if payload.get("action") == "TOGGLE_FOW":
            if self.fow_manager:
                self.fow_manager.is_disabled = not self.fow_manager.is_disabled
                self.fow_layer.is_dirty = True
                state = "OFF" if self.fow_manager.is_disabled else "ON"
                self.notifications.add_notification(f"GM: Fog of War {state}")

        if payload.get("action") == "TOGGLE_DOOR":
            door_layer = payload.get("door")
            if door_layer:
                # Toggle door in visibility engine
                found = False
                for blocker in self.visibility_engine.blockers:
                    if blocker.layer_name == door_layer:
                        blocker.is_open = not blocker.is_open
                        found = True
                if found:
                    self.visibility_engine.update_blockers(
                        self.visibility_engine.blockers
                    )
                    self.notifications.add_notification(f"Door {door_layer} Toggled")
                    self.save_session()  # Persist door state

    def switch_to_viewing(self):
        """Switches the current scene to ViewingScene."""
        if SceneId.VIEWING in self.scenes:
            target_scene = self.scenes[SceneId.VIEWING]
            if self.current_scene != target_scene:
                self.current_scene.on_exit()
                self.current_scene = target_scene
                self.current_scene.on_enter()

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        filename = os.path.abspath(filename)
        self.map_system.svg_loader = SVGLoader(filename)
        self.state.increment_map_timestamp()

        # Update Visibility Engine with blockers
        blockers = self.map_system.svg_loader.get_visibility_blockers()

        entry = self.map_config.data.maps.get(filename)
        if entry is None:
            from light_map.map_config import MapEntry

            self.map_config.data.maps[filename] = MapEntry()
            entry = self.map_config.data.maps[filename]

        # Automatically detect grid spacing if not already set
        if entry.grid_spacing_svg <= 0:
            spacing, ox, oy = self.map_system.svg_loader.detect_grid_spacing()
            if spacing > 0:
                logging.info(
                    f"Auto-detected grid for {filename}: spacing={spacing:.1f}, origin=({ox:.1f}, {oy:.1f})"
                )
                entry.grid_spacing_svg = spacing
                entry.grid_origin_svg_x = ox
                entry.grid_origin_svg_y = oy

                # Calculate initial base scale for this map
                ppi = self.map_config.get_ppi()
                if ppi > 0:
                    entry.scale_factor_1to1 = (
                        entry.physical_unit_inches * ppi
                    ) / spacing
                self.map_config.save()

        # Setup Visibility Engine with correct scaling
        self.visibility_engine = VisibilityEngine(
            grid_spacing_svg=entry.grid_spacing_svg or 10.0,
            grid_origin=(entry.grid_origin_svg_x, entry.grid_origin_svg_y),
        )
        self.visibility_engine.update_blockers(blockers)

        # Setup FoW Layer with persistence
        fow_dir = os.path.join(
            os.path.expanduser("~"), ".light_map", "maps", os.path.basename(filename)
        )
        fow_path = os.path.join(fow_dir, "fow.png")

        # Calculate mask dimensions based on 16x grid resolution
        # SVG width/height in units
        svg_w = self.map_system.svg_loader.svg.width
        svg_h = self.map_system.svg_loader.svg.height
        mask_w = (
            int((svg_w / entry.grid_spacing_svg) * 16)
            if entry.grid_spacing_svg > 0
            else self.config.width
        )
        mask_h = (
            int((svg_h / entry.grid_spacing_svg) * 16)
            if entry.grid_spacing_svg > 0
            else self.config.height
        )

        self.fow_manager = FogOfWarManager(mask_w, mask_h, file_path=fow_path)
        self.fow_layer = FogOfWarLayer(self.fow_manager)
        # Update layer in stack (it might have been replaced)
        self.layer_stack[1] = self.fow_layer
        self.visibility_layer = VisibilityLayer(self.state, mask_w, mask_h)
        self.layer_stack[2] = self.visibility_layer

        if load_session:
            session_dir = None
            if self.config.storage_manager:
                session_dir = os.path.join(
                    self.config.storage_manager.get_data_dir(), "sessions"
                )
            session = SessionManager.load_for_map(filename, session_dir=session_dir)
            if session:
                self.map_system.ghost_tokens = session.tokens
                self.state.tokens = session.tokens
                self.state.tokens_timestamp += 1

                # Restore door states
                for blocker in self.visibility_engine.blockers:
                    if blocker.layer_name in session.door_states:
                        blocker.is_open = session.door_states[blocker.layer_name]
                self.visibility_engine.update_blockers(self.visibility_engine.blockers)

                if session.viewport:
                    self.map_system.set_state(
                        session.viewport.x,
                        session.viewport.y,
                        session.viewport.zoom,
                        session.viewport.rotation,
                    )
                self.map_config.data.global_settings.last_used_map = filename
                self.map_config.save()
                self.switch_to_viewing()
                return

        # Default loading if no session or session load failed
        vp = self.map_config.get_map_viewport(filename)
        self.map_system.set_state(vp.x, vp.y, vp.zoom, vp.rotation)

        # Calculate and set base scale (1:1 zoom level)
        # If we have grid info, we can always derive the correct scale from PPI.
        # This handles changes in PPI (projector height/model) automatically.
        ppi = self.map_config.get_ppi()
        if entry and entry.grid_spacing_svg > 0 and ppi > 0:
            self.map_system.base_scale = (
                entry.physical_unit_inches * ppi
            ) / entry.grid_spacing_svg
        else:
            self.map_system.base_scale = (
                entry.scale_factor_1to1 if entry and entry.scale_factor_1to1 > 0 else 1.0
            )

        self.map_config.data.global_settings.last_used_map = filename
        self.map_config.save()

        # Switch to Viewing Scene to ensure map is visible
        self.switch_to_viewing()

    def refresh_base_scale(self):
        """Recalculates the base scale for the currently loaded map based on current PPI."""
        if not self.map_system.is_map_loaded():
            return

        filename = self.map_system.svg_loader.filename
        entry = self.map_config.data.maps.get(filename)
        ppi = self.map_config.get_ppi()

        if entry and entry.grid_spacing_svg > 0 and ppi > 0:
            self.map_system.base_scale = (
                entry.physical_unit_inches * ppi
            ) / entry.grid_spacing_svg
            logging.info(
                f"Refreshed base scale for {os.path.basename(filename)}: {self.map_system.base_scale:.4f} (PPI={ppi:.1f})"
            )
        elif entry:
            self.map_system.base_scale = (
                entry.scale_factor_1to1 if entry.scale_factor_1to1 > 0 else 1.0
            )

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

        # Collect current door states
        door_states = {
            b.layer_name: b.is_open
            for b in self.visibility_engine.blockers
            if b.type == "door"
        }

        session = SessionData(
            map_file=map_file,
            viewport=ViewportState(
                x=self.map_system.state.x,
                y=self.map_system.state.y,
                zoom=self.map_system.state.zoom,
                rotation=self.map_system.state.rotation,
            ),
            tokens=self.map_system.ghost_tokens,
            door_states=door_states,
        )
        SessionManager.save_for_map(map_file, session, session_dir=session_dir)
