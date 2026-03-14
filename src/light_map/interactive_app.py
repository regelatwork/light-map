from __future__ import annotations
import numpy as np
import time
import os
import sys
import logging
from typing import List, Tuple, Any, Dict, Optional, TYPE_CHECKING, Callable

from light_map.common_types import (
    AppConfig,
    Layer,
    SceneId,
)
from light_map.renderer import Renderer
from light_map.map_system import MapSystem
from light_map.svg import SVGLoader
from light_map.map_config import MapConfigManager
from light_map.session_manager import SessionManager
from light_map.fow_manager import FogOfWarManager
from light_map.visibility_engine import VisibilityEngine

from light_map.core.app_context import AppContext
from light_map.core.analytics import AnalyticsManager
from light_map.core.notification import NotificationManager
from light_map.core.layer_stack_manager import LayerStackManager
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


from light_map.core.temporal_event_manager import TemporalEventManager


class InteractiveApp:
    def __init__(
        self,
        config: AppConfig,
        time_provider=time.monotonic,
        events: Optional[TemporalEventManager] = None,
    ):
        self.config = config
        self.time_provider = time_provider
        self.events = events or TemporalEventManager(time_provider=time_provider)
        self.last_fps_time = 0.0
        self.fps = 0.0
        self.last_scene_version = -1

        # State management
        self.state = WorldState()

        # Core Systems
        self.renderer = Renderer(config.width, config.height)
        self.map_system = MapSystem(config.width, config.height)
        self.map_config = MapConfigManager(storage=config.storage_manager)
        self.notifications = NotificationManager()

        # Sync AppConfig with MapConfig global settings
        gs = self.map_config.data.global_settings
        self.config.enable_hand_masking = gs.enable_hand_masking
        self.config.hand_mask_padding = gs.hand_mask_padding
        self.config.gm_position = gs.gm_position
        self.config.projector_ppi = gs.projector_ppi
        self.config.inspection_linger_duration = gs.inspection_linger_duration
        self.config.door_thickness_multiplier = gs.door_thickness_multiplier

        # Visibility and FoW Systems
        # Use a temporary engine until map is loaded
        self.visibility_engine = VisibilityEngine(grid_spacing_svg=10.0)
        self.fow_manager = FogOfWarManager(config.width, config.height)
        self.inspected_token_id: Optional[int] = None
        self.current_map_path: Optional[str] = None

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

        # Layer Management
        self.layer_manager = LayerStackManager(self.app_context, self.state)
        self.layer_manager.update_visibility_stack(
            self.fow_manager,
            config.width,
            config.height,
            spacing=10.0,
            origin=(0.0, 0.0),
        )

        # Scene Management
        self.scenes = self._initialize_scenes()
        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()

    def get_layer_stack(self) -> List[Layer]:
        """
        Returns the optimized layer stack for the current scene and state.
        Ensures correct ordering (e.g. Menu on top of Tokens).
        """
        return self.layer_manager.get_stack(self.current_scene)

    @property
    def layer_stack(self) -> List[Layer]:
        return self.layer_manager.layer_stack

    @property
    def map_layer(self):
        return self.layer_manager.map_layer

    @property
    def door_layer(self):
        return self.layer_manager.door_layer

    @property
    def fow_layer(self):
        return self.layer_manager.fow_layer

    @property
    def visibility_layer(self):
        return self.layer_manager.visibility_layer

    @property
    def scene_layer(self):
        return self.layer_manager.scene_layer

    @property
    def hand_mask_layer(self):
        return self.layer_manager.hand_mask_layer

    @property
    def menu_layer(self):
        return self.layer_manager.menu_layer

    @property
    def token_layer(self):
        return self.layer_manager.token_layer

    @property
    def notification_layer(self):
        return self.layer_manager.notification_layer

    @property
    def debug_layer(self):
        return self.layer_manager.debug_layer

    @property
    def cursor_layer(self):
        return self.layer_manager.cursor_layer

    @property
    def exclusive_vision_layer(self):
        return self.layer_manager.exclusive_vision_layer

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
                "  PLEASE RUN: python3 scripts/projector_calibration.py\n"
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
            visibility_engine=self.visibility_engine,
            aruco_detector=aruco_detector,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            camera_rvec=rvec,
            camera_tvec=tvec,
            debug_mode=debug_mode,
            show_tokens=show_tokens,
            raw_tokens=self.state.raw_tokens,
            state=self.state,
            analytics=AnalyticsManager(self.config.storage_manager),
            events=self.events,
            save_session=self.save_session,
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

        # Re-initialize Layer Management
        self.layer_manager = LayerStackManager(self.app_context, self.state)
        # Use current visibility params if map is loaded, else default
        if self.current_map_path:
            entry = self.map_config.data.maps.get(self.current_map_path)
            if entry:
                self.layer_manager.update_visibility_stack(
                    self.fow_manager,
                    self.fow_manager.width if self.fow_manager else self.config.width,
                    self.fow_manager.height if self.fow_manager else self.config.height,
                    spacing=entry.grid_spacing_svg,
                    origin=(entry.grid_origin_svg_x, entry.grid_origin_svg_y),
                )
        else:
            self.layer_manager.update_visibility_stack(
                self.fow_manager,
                self.config.width,
                self.config.height,
                spacing=10.0,
                origin=(0.0, 0.0),
            )

        self.scenes = self._initialize_scenes()
        self.current_scene = self.scenes[SceneId.MENU]
        self.current_scene.on_enter()
        self.notifications.add_notification("Configuration Reloaded")

    def _switch_scene(self, transition):
        target_id = transition.target_scene
        if target_id in self.scenes:
            logging.debug("Switching scene to: %s", target_id)
            self.current_scene.on_exit()
            self.current_scene = self.scenes[target_id]
            self.last_scene_version = -1  # Reset version tracking for new scene
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
            self.layer_manager.update_state(state)

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

        # Trigger pruning and update timestamp
        self.app_context.notifications.get_active_notifications()
        state.notifications_timestamp = self.app_context.notifications.timestamp

        state.update_viewport(self.map_system.state.to_viewport())

        # Update token screen coordinates for external consumers (like remote driver)
        for token in state.tokens:
            token.screen_x, token.screen_y = self.map_system.world_to_screen(
                token.world_x, token.world_y
            )

        # Process Remote Actions
        if state.pending_actions:
            for action_data in state.pending_actions:
                action_name = action_data.get("action")
                if action_name == "ZOOM":
                    delta = action_data.get("delta", 0.0)
                    self.map_system.zoom_pinned(
                        1.0 + delta, (self.config.width // 2, self.config.height // 2)
                    )
                elif action_name == "UPDATE_TOKEN":
                    token_id = action_data.get("id")
                    if token_id is not None:
                        # Try to get existing definition to preserve fields
                        # Priority: Map Override > Global Default
                        existing_def = None
                        is_map_override = False

                        map_file = self.current_map_path
                        if map_file:
                            map_entry = self.map_config.data.maps.get(map_file)
                            if map_entry:
                                existing_def = map_entry.aruco_overrides.get(token_id)
                                if existing_def:
                                    is_map_override = True

                        # Explicit override from action data (if provided)
                        action_override = action_data.get("is_map_override")
                        if action_override is not None:
                            is_map_override = action_override

                        if not existing_def:
                            existing_def = (
                                self.map_config.data.global_settings.aruco_defaults.get(
                                    token_id
                                )
                            )

                        new_name = action_data.get("name")
                        new_color = action_data.get("color")
                        new_type = action_data.get("type")
                        new_profile = action_data.get("profile")
                        new_size = action_data.get("size")
                        new_height_mm = action_data.get("height_mm")

                        # Use existing values if not provided in the update
                        final_name = (
                            new_name
                            if new_name is not None
                            else (
                                existing_def.name
                                if existing_def
                                else f"Token {token_id}"
                            )
                        )
                        final_type = (
                            new_type
                            if new_type is not None
                            else (existing_def.type if existing_def else "NPC")
                        )
                        final_profile = (
                            new_profile
                            if new_profile is not None
                            else (existing_def.profile if existing_def else None)
                        )
                        final_size = (
                            new_size
                            if new_size is not None
                            else (existing_def.size if existing_def else None)
                        )
                        final_height_mm = (
                            new_height_mm
                            if new_height_mm is not None
                            else (existing_def.height_mm if existing_def else None)
                        )
                        final_color = (
                            new_color
                            if new_color is not None
                            else (existing_def.color if existing_def else None)
                        )

                        if is_map_override and map_file:
                            self.map_config.set_map_aruco_override(
                                map_name=map_file,
                                aruco_id=token_id,
                                name=final_name,
                                type=final_type,
                                profile=final_profile,
                                size=final_size,
                                height_mm=final_height_mm,
                                color=final_color,
                            )
                            logging.info(
                                f"InteractiveApp: Updated MAP override for token {token_id} on {os.path.basename(map_file)}"
                            )
                        else:
                            self.map_config.set_global_aruco_definition(
                                aruco_id=token_id,
                                name=final_name,
                                type=final_type,
                                profile=final_profile,
                                size=final_size,
                                height_mm=final_height_mm,
                                color=final_color,
                            )
                            logging.info(
                                f"InteractiveApp: Updated GLOBAL definition for token {token_id}"
                            )
                elif action_name == "DELETE_TOKEN_OVERRIDE":
                    token_id = action_data.get("id")
                    map_file = self.current_map_path
                    if token_id is not None and map_file:
                        self.map_config.delete_map_aruco_override(map_file, token_id)
                        logging.info(
                            f"InteractiveApp: Deleted MAP override for token {token_id} on {os.path.basename(map_file)}"
                        )
                elif action_name == "DELETE_TOKEN":
                    token_id = action_data.get("id")
                    if token_id is not None:
                        self.map_config.delete_global_aruco_definition(token_id)
                        logging.info(
                            f"InteractiveApp: Deleted GLOBAL definition for token {token_id}"
                        )

                elif action_name == "MENU_INTERACT":
                    # Use class name check to avoid potential double-import/instance-check issues
                    is_menu_scene = self.current_scene.__class__.__name__ == "MenuScene"

                    logging.debug(
                        f"InteractiveApp: Received MENU_INTERACT index={action_data.get('index')}, current_scene={self.current_scene.__class__.__name__}"
                    )

                    if is_menu_scene:
                        index = action_data.get("index")
                        if index is not None:
                            # Safely access menu_system (expected on MenuScene)
                            menu_sys = getattr(self.current_scene, "menu_system", None)
                            if menu_sys:
                                menu_sys.trigger_index(index)
                                self.current_scene.mark_dirty()
                            else:
                                logging.error(
                                    "InteractiveApp: Current scene is MenuScene but has no menu_system"
                                )
                    else:
                        logging.warning(
                            f"InteractiveApp: MENU_INTERACT ignored - current scene {self.current_scene.__class__.__name__} is not MenuScene"
                        )
                else:
                    # Generic action/payload for SYNC_VISION, etc.

                    transition = self._handle_payloads(action_data, state)
                    if transition:
                        self._switch_scene(transition)
                    else:
                        # If not handled by _handle_payloads, pass it as a semantic action to the scene
                        if actions is not None:
                            actions.append(action_name)
            state.pending_actions.clear()

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
            # BUG-FIX: Expire inputs if no update received for > 0.5s
            if inputs and (current_time - state.last_hand_timestamp > 0.5):
                state.inputs = []
                state.hands_timestamp += 1
                inputs = []

        # Update app context with latest vision results
        self.app_context.last_camera_frame = state.background
        self.app_context.raw_aruco = state.raw_aruco
        self.app_context.raw_tokens = state.raw_tokens
        self.inspected_token_id = self.app_context.inspected_token_id

        # Update dwell state if available in current scene
        dwell_tracker = getattr(self.current_scene, "dwell_tracker", None)
        if dwell_tracker:
            state.dwell_state = {
                "accumulated_time": dwell_tracker.accumulated_time,
                "is_triggered": dwell_tracker.is_triggered,
                "last_point": dwell_tracker.last_point,
                "target_id": dwell_tracker.target_id,  # Use internal tracker's target_id
            }
        else:
            state.dwell_state = {}

        # --- VISIBILITY AND LAYER STACK ---
        current_stack = self.get_layer_stack()

        # Handle Exclusive Vision (Token Inspection) - Opacity logic only
        if (
            self.inspected_token_id is not None
            and self.app_context.inspected_token_mask is not None
        ):
            # Ensure Map is full brightness
            if self.layer_manager.map_layer.opacity != 1.0:
                self.layer_manager.map_layer.opacity = 1.0
                self.layer_manager.map_layer._version += 1
        else:
            self.app_context.inspected_token_mask = None

        # We need to update tokens in map system from state
        self.map_system.ghost_tokens = state.tokens

        # Scene Update
        transition = self.current_scene.update(inputs, actions, current_time)
        if transition:
            self._handle_payloads(transition.payload, state)
            self._switch_scene(transition)

        # Sync Menu State to WorldState

        menu_state = getattr(self.current_scene, "menu_state", None)
        state.update_menu_state(menu_state)

        # --- LAYERED RENDERING ---
        with track_wait("total_render_logic", self.instrument):
            t_start = time.perf_counter_ns()

            # 1. Update MapLayer params based on scene
            new_opacity = 1.0
            is_interacting = getattr(self.current_scene, "is_interacting", False)
            new_quality = 0.25 if is_interacting else 1.0

            if (
                new_opacity != self.layer_manager.map_layer.opacity
                or new_quality != self.layer_manager.map_layer.quality
            ):
                self.layer_manager.map_layer.opacity = new_opacity
                self.layer_manager.map_layer.quality = new_quality
                self.layer_manager.map_layer._version += 1

            # 2. Update SceneLayer bridge
            self.layer_manager.scene_layer.scene = self.current_scene
            # Only increment scene timestamp if scene is actually dirty
            if (
                self.current_scene.is_dynamic
                or self.current_scene.version != self.last_scene_version
            ):
                state.increment_scene_timestamp()
                self.last_scene_version = self.current_scene.version

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

    def _sync_vision(self, state: "WorldState"):
        """Forces a line-of-sight visibility sync."""
        if (
            self.visibility_engine
            and self.fow_manager
            and self.current_map_path
            and state is not None
        ):
            # Calculate latest vision mask on-demand
            combined_pc_mask = self.visibility_engine.get_aggregate_vision_mask(
                state.tokens,
                self.map_config,
                self.fow_manager.width,
                self.fow_manager.height,
                vision_range_grid=25.0,
            )

            if combined_pc_mask is not None:
                # 1. Update Persistent Fog of War (Explore new areas)
                self.fow_manager.reveal_area(combined_pc_mask)

                # 2. Update Visible Line-of-Sight (the 'clear holes')
                self.fow_manager.set_visible_mask(combined_pc_mask)

                # 3. Save both to stable storage
                self.map_config.save_fow_masks(self.current_map_path, self.fow_manager)

                # 4. Update VisibilityLayer (the highlight)
                self.state.update_visibility_mask(combined_pc_mask)

                # 5. Invalidate Layer Caches
                self.state.increment_fow_timestamp()

    def _rebuild_visibility_stack(self, entry: Any):
        """Re-initializes visibility engine and layers based on map configuration."""
        spacing = entry.grid_spacing_svg if entry.grid_spacing_svg > 0 else 10.0
        origin = (entry.grid_origin_svg_x, entry.grid_origin_svg_y)

        self.visibility_engine = VisibilityEngine(
            grid_spacing_svg=spacing,
            grid_origin=origin,
        )
        self.app_context.visibility_engine = self.visibility_engine

        # Sync to WorldState
        self.state.grid_spacing_svg = spacing
        self.state.grid_origin_svg_x = entry.grid_origin_svg_x
        self.state.grid_origin_svg_y = entry.grid_origin_svg_y

        # Re-initialize blockers with new visibility engine parameters
        blockers = self.map_system.svg_loader.get_visibility_blockers()
        svg_w = self.map_system.svg_loader.svg.width
        svg_h = self.map_system.svg_loader.svg.height
        mask_w, mask_h = self.visibility_engine.calculate_mask_dimensions(svg_w, svg_h)
        self.visibility_engine.update_blockers(blockers, mask_w, mask_h)

        # Re-initialize Fog of War Manager if not already done for this map
        # Or if dimensions changed (which shouldn't happen for same map file)
        if (
            self.fow_manager is None
            or self.fow_manager.width != mask_w
            or self.fow_manager.height != mask_h
        ):
            self.fow_manager = FogOfWarManager(mask_w, mask_h)
            if self.current_map_path:
                self.map_config.load_fow_masks(self.current_map_path, self.fow_manager)

        # Update layers via manager
        self.layer_manager.update_visibility_stack(
            self.fow_manager,
            mask_w,
            mask_h,
            spacing,
            origin,
        )

        # Sync blockers to state
        self._sync_blockers_to_state()

    def _sync_blockers_to_state(self):
        """Synchronizes visibility engine blockers to the public state."""
        self.state.blockers = [
            {
                "id": b.id,
                "type": b.type.value if hasattr(b.type, "value") else str(b.type),
                "is_open": b.is_open,
                "points": b.segments,
            }
            for b in self.visibility_engine.blockers
        ]
        self.state.visibility_timestamp += 1

    def _handle_payloads(self, payload: Any, state: Optional["WorldState"] = None):
        """Handle side-effects from scene transitions, like loading maps."""
        if not isinstance(payload, dict):
            return

        if "map_file" in payload:
            self.load_map(payload["map_file"], payload.get("load_session", False))

        action_name = payload.get("action")
        if action_name == "SYNC_VISION":
            if state is not None:
                self._sync_vision(state)
            self.app_context.notifications.add_notification("Vision Synchronized")
        elif action_name == "RESET_ZOOM":
            self.map_system.reset_zoom_to_base()
            self.notifications.add_notification("Zoom Reset to 1:1")
        elif action_name == "UPDATE_GRID":
            if self.current_map_path:
                entry = self.map_config.data.maps.get(self.current_map_path)
                if entry:
                    entry.grid_origin_svg_x = payload.get("offset_x", 0.0)
                    entry.grid_origin_svg_y = payload.get("offset_y", 0.0)

                    spacing = payload.get("spacing")
                    if spacing is not None and spacing > 0:
                        entry.grid_spacing_svg = spacing
                        # Recalculate base scale if spacing changed
                        self.refresh_base_scale()

                    self.map_config.save()

                    # Update WorldState
                    self.state.grid_origin_svg_x = entry.grid_origin_svg_x
                    self.state.grid_origin_svg_y = entry.grid_origin_svg_y
                    self.state.grid_spacing_svg = entry.grid_spacing_svg

                    # Re-setup visibility stack
                    self._rebuild_visibility_stack(entry)
                    self.notifications.add_notification("Grid Configuration Updated")
        elif action_name == "INJECT_HANDS_WORLD":
            from .core.scene import HandInput
            from .common_types import GestureType

            hands_data = payload.get("hands", [])
            processed_hands = []
            for h in hands_data:
                sx, sy = self.map_system.world_to_screen(h["world_x"], h["world_y"])
                gesture_str = h.get("gesture", "NONE").upper()
                try:
                    gesture = GestureType[gesture_str]
                except KeyError:
                    gesture = GestureType.NONE
                processed_hands.append(
                    HandInput(
                        gesture=gesture,
                        proj_pos=(int(sx), int(sy)),
                        unit_direction=(0.0, 0.0),
                        raw_landmarks=None,
                    )
                )
            if state is not None:
                state.update_inputs(processed_hands, self.time_provider())
        elif action_name == "SET_VIEWPORT":
            if "zoom" in payload:
                self.map_system.state.zoom = payload["zoom"]
            if "pan_x" in payload and "pan_y" in payload:
                self.map_system.state.pan_x = payload["pan_x"]
                self.map_system.state.pan_y = payload["pan_y"]
            if "rotation" in payload:
                self.map_system.state.rotation = payload["rotation"]

        if payload.get("action") == "RESET_FOW":
            if self.fow_manager and self.current_map_path:
                self.fow_manager.reset()
                self.map_config.save_fow_masks(self.current_map_path, self.fow_manager)
                self.state.increment_fow_timestamp()
                self.notifications.add_notification("Fog of War Reset")

        if payload.get("action") == "TOGGLE_FOW":
            if self.fow_manager:
                self.fow_manager.is_disabled = not self.fow_manager.is_disabled
                self.state.increment_fow_timestamp()
                state = "OFF" if self.fow_manager.is_disabled else "ON"
                self.notifications.add_notification(f"GM: Fog of War {state}")

        if payload.get("action") == "TOGGLE_HAND_MASKING":
            gs = self.map_config.data.global_settings
            gs.enable_hand_masking = not gs.enable_hand_masking
            self.map_config.save()
            self.config.enable_hand_masking = gs.enable_hand_masking
            state_str = "ON" if gs.enable_hand_masking else "OFF"
            self.notifications.add_notification(f"Projection Masking {state_str}")

        if payload.get("action") == "SET_GM_POSITION":
            from light_map.common_types import GmPosition

            try:
                new_pos = GmPosition(payload.get("payload", "None"))
                gs = self.map_config.data.global_settings
                gs.gm_position = new_pos
                self.map_config.save()
                self.config.gm_position = gs.gm_position
                self.notifications.add_notification(f"GM Position: {new_pos}")
            except (ValueError, KeyError):
                self.notifications.add_notification("Invalid GM Position")

        if payload.get("action") == "TOGGLE_DEBUG_MODE":
            self.app_context.debug_mode = not self.app_context.debug_mode
            state_str = "ON" if self.app_context.debug_mode else "OFF"
            self.notifications.add_notification(f"Debug Mode {state_str}")

        if payload.get("action") == "INSPECT_TOKEN":
            token_id_str = payload.get("payload")
            if token_id_str is not None:
                try:
                    token_id = int(token_id_str)
                    target_token = None
                    if state is not None:
                        for t in state.tokens:
                            if t.id == token_id:
                                target_token = t
                                break
                        if not target_token:
                            for t in state.raw_tokens:
                                if t.id == token_id:
                                    target_token = t
                                    break

                    if target_token:
                        self.app_context.inspected_token_id = token_id
                        map_file = (
                            self.map_system.svg_loader.filename
                            if self.map_system.svg_loader
                            else None
                        )
                        resolved = self.map_config.resolve_token_profile(
                            token_id, map_file
                        )
                        self.notifications.add_notification(
                            f"Inspecting: {resolved.name}"
                        )

                        if self.visibility_engine and self.map_system.is_map_loaded():
                            engine = self.visibility_engine
                            self.app_context.inspected_token_mask = (
                                engine.get_token_vision_mask(
                                    token_id,
                                    target_token.world_x,
                                    target_token.world_y,
                                    size=resolved.size,
                                    vision_range_grid=25.0,
                                    mask_width=engine.width,
                                    mask_height=engine.height,
                                )
                            )
                except ValueError:
                    pass

        if payload.get("action") == "CLEAR_INSPECTION":
            self.app_context.inspected_token_id = None
            self.app_context.inspected_token_mask = None

        if payload.get("action") == "TOGGLE_DOOR":
            from light_map.common_types import SelectionType

            # If a specific door is passed in the payload, select it first
            # RemoteDriver's inject_action puts the payload in the 'payload' field
            door_id = payload.get("door_id") or payload.get("payload")
            if door_id:
                self.state.selection.type = SelectionType.DOOR
                self.state.selection.id = door_id

            if (
                self.state.selection.type == SelectionType.DOOR
                and self.state.selection.id
            ):
                door_id = self.state.selection.id
                # Toggle door in visibility engine
                found = False
                for blocker in self.visibility_engine.blockers:
                    if blocker.id == door_id:
                        blocker.is_open = not blocker.is_open
                        found = True
                if found:
                    self.visibility_engine.update_blockers(
                        self.visibility_engine.blockers,
                        self.fow_manager.width,
                        self.fow_manager.height,
                    )
                    # Sync state.blockers so frontend gets updated is_open status
                    self._sync_blockers_to_state()

                    self.notifications.add_notification(f"Door {door_id} Toggled")
                    self.save_session()  # Persist door state

                    # Sync vision immediately when a door is toggled
                    if state is not None:
                        self._sync_vision(state)
            else:
                self.notifications.add_notification("No door selected to toggle")

        from .common_types import MenuActions, SceneId
        from .core.scene import SceneTransition

        action_name = payload.get("action")
        if action_name in [
            MenuActions.CALIBRATE_INTRINSICS,
            MenuActions.CALIBRATE_PROJECTOR,
            MenuActions.CALIBRATE_PPI,
            MenuActions.CALIBRATE_EXTRINSICS,
            MenuActions.CALIBRATE_FLASH,
            MenuActions.SET_MAP_SCALE,
            MenuActions.CALIBRATE_SCALE,
            "SCAN_SESSION",
        ]:
            scene_map = {
                MenuActions.CALIBRATE_INTRINSICS: SceneId.CALIBRATE_INTRINSICS,
                MenuActions.CALIBRATE_PROJECTOR: SceneId.CALIBRATE_PROJECTOR,
                MenuActions.CALIBRATE_PPI: SceneId.CALIBRATE_PPI,
                MenuActions.CALIBRATE_EXTRINSICS: SceneId.CALIBRATE_EXTRINSICS,
                MenuActions.CALIBRATE_FLASH: SceneId.CALIBRATE_FLASH,
                MenuActions.SET_MAP_SCALE: SceneId.CALIBRATE_MAP_GRID,
                MenuActions.CALIBRATE_SCALE: SceneId.CALIBRATE_MAP_GRID,
                "SCAN_SESSION": SceneId.SCANNING,
            }
            if action_name == "SCAN_SESSION" and not self.map_system.is_map_loaded():
                self.notifications.add_notification("Load a map before scanning.")
                return None
            return SceneTransition(scene_map[action_name])

        return None

    def switch_to_viewing(self):
        """Switches the current scene to ViewingScene."""
        if SceneId.VIEWING in self.scenes:
            target_scene = self.scenes[SceneId.VIEWING]
            if self.current_scene != target_scene:
                self.current_scene.on_exit()
                self.current_scene = target_scene
                self.last_scene_version = -1
                self.current_scene.on_enter()

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        filename = os.path.abspath(filename)
        self.current_map_path = filename
        self.map_system.svg_loader = SVGLoader(filename)
        self.state.increment_map_timestamp()

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

        # setup Visibility Engine and layers
        self._rebuild_visibility_stack(entry)

        # Restore Visibility Highlight in state if loaded from persistence
        if np.any(self.fow_manager.visible_mask):
            self.state.update_visibility_mask(self.fow_manager.visible_mask)

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

                from light_map.visibility_types import VisibilityType

                # Restore door states
                for blocker in self.visibility_engine.blockers:
                    if (
                        blocker.type == VisibilityType.DOOR
                        and blocker.id in session.door_states
                    ):
                        blocker.is_open = session.door_states[blocker.id]
                self.visibility_engine.update_blockers(
                    self.visibility_engine.blockers,
                    self.fow_manager.width,
                    self.fow_manager.height,
                )
                # Sync state.blockers so frontend gets updated is_open status
                self._sync_blockers_to_state()

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
                entry.scale_factor_1to1
                if entry and entry.scale_factor_1to1 > 0
                else 1.0
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

        from light_map.visibility_types import VisibilityType

        # Collect current door states
        door_states = {
            b.id: b.is_open
            for b in self.visibility_engine.blockers
            if b.type == VisibilityType.DOOR
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
