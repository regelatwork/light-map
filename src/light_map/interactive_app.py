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
    TimerKey,
    GridMetadata,
    MapRenderState,
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
from light_map.scenes.exclusive_vision_scene import ExclusiveVisionScene
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
    Projector3DCalibrationScene,
)


from light_map.vision.tracking_coordinator import TrackingCoordinator
from light_map.vision.input_processor import InputProcessor
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.vision.projection import (
    Projector3DModel,
    CameraProjectionModel,
    ProjectionService,
)

from light_map.core.world_state import WorldState

if TYPE_CHECKING:
    from light_map.common_types import Action, Token
    from light_map.core.scene import SceneTransition


from light_map.core.temporal_event_manager import TemporalEventManager
from light_map.action_dispatcher import ActionDispatcher
from light_map.input_coordinator import InputCoordinator


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
        self.events.state = self.state

        # Core Systems
        self.map_config = MapConfigManager(storage=config.storage_manager)
        self.notifications = NotificationManager(
            time_provider=time_provider,
            events=self.events,
            atom=self.state._notifications_atom,
        )

        # Initialize Projector 3D Model
        self.config.projector_3d_model = Projector3DModel.load_from_storage(
            config.storage_manager,
            use_3d=self.map_config.data.global_settings.use_projector_3d_model,
        )

        self.renderer = Renderer(config, self.config.projector_3d_model)
        self.map_system = MapSystem(config)

        # Sync AppConfig with MapConfig global settings
        self.config.sync_from_global_settings(self.map_config.data.global_settings)

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
        self.action_dispatcher = ActionDispatcher(self)
        self.input_coordinator = InputCoordinator(self)

        # Load Camera Calibration
        camera_matrix, distortion_coefficients, rotation_vector, translation_vector = (
            self._load_camera_calibration()
        )

        # Normalize calibration if resolution mismatch
        camera_matrix, rotation_vector, translation_vector = (
            self._normalize_calibration(
                camera_matrix, rotation_vector, translation_vector
            )
        )

        # Sync calibration to config
        self.config.camera_matrix = camera_matrix
        self.config.distortion_coefficients = distortion_coefficients
        self.config.rotation_vector = rotation_vector
        self.config.translation_vector = translation_vector

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # AppContext (shared state for scenes)
        # Sync calibration to background tracker
        self.tracking_coordinator.token_tracker.set_aruco_calibration(
            camera_matrix, distortion_coefficients, rotation_vector, translation_vector
        )

        self.app_context = self._create_app_context(
            debug_mode=False,
            show_tokens=True,
        )

        # Layer Management
        self.layer_manager = LayerStackManager(self.app_context, self.state)
        self.app_context.layer_manager = self.layer_manager
        self.layer_manager.update_visibility_stack(
            self.fow_manager,
            config.width,
            config.height,
            spacing=10.0,
            origin=(0.0, 0.0),
        )

        # Scene Management
        self.scenes = self._initialize_scenes()

        # Initialize Projector Pose Atom with current absolute position
        calibrated_pos = self.config.projector_3d_model.calibrated_projector_center
        if calibrated_pos is not None:
            from .common_types import ProjectorPose

            gs = self.map_config.data.global_settings
            self.state.projector_pose = ProjectorPose(
                x=gs.projector_pos_x_override
                if gs.projector_pos_x_override is not None
                else calibrated_pos[0],
                y=gs.projector_pos_y_override
                if gs.projector_pos_y_override is not None
                else calibrated_pos[1],
                z=gs.projector_pos_z_override
                if gs.projector_pos_z_override is not None
                else calibrated_pos[2],
            )

        self.current_scene: Scene = self.scenes[SceneId.MENU]
        self.current_scene_name = self.current_scene.__class__.__name__
        self.state.current_scene_name = self.current_scene_name
        self.state.update_performance_metrics(0.0)
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
    def aruco_mask_layer(self):
        return self.layer_manager.aruco_mask_layer

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
        self,
        camera_matrix: np.ndarray,
        rotation_vector: np.ndarray,
        translation_vector: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Normalizes camera_matrix and projector_matrix if the current camera resolution
        differs from the resolution used during calibration.
        """
        cam_w, cam_h = self.config.camera_resolution
        calib_w, calib_h = self.config.projector_matrix_resolution

        if cam_w == 0 or calib_w == 0:
            return camera_matrix, rotation_vector, translation_vector

        if cam_w == calib_w and cam_h == calib_h:
            return camera_matrix, rotation_vector, translation_vector

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

        scale_matrix = np.array(
            [[inv_scale_x, 0, 0], [0, inv_scale_y, 0], [0, 0, 1]], dtype=np.float32
        )

        self.config.projector_matrix = self.config.projector_matrix @ scale_matrix

        return new_camera_matrix, rotation_vector, translation_vector

    def _load_camera_calibration(
        self,
    ) -> Tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
    ]:
        camera_matrix = None
        distortion_coefficients = None
        rotation_vector = None
        translation_vector = None

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
            missing_str = ", ".join(str(m) for m in missing)
            msg = (
                "\n" + "!" * 60 + "\n"
                "CRITICAL ERROR: Camera Calibration Files Missing!\n"
                f"  Missing files: {missing_str}\n"
                "  The system cannot map tokens without camera calibration.\n"
                "  PLEASE RUN: python3 scripts/projector_calibration.py\n"
                "!" * 60 + "\n"
            )
            logging.critical(msg)
            sys.exit(1)

        try:
            intrinsics_data = np.load(intrinsics_path)
            camera_matrix = intrinsics_data.get("camera_matrix")
            if camera_matrix is None:
                camera_matrix = intrinsics_data.get("mtx")
            distortion_coefficients = intrinsics_data.get("distortion_coefficients")
            if distortion_coefficients is None:
                distortion_coefficients = intrinsics_data.get("dist_coeffs")
            logging.info("Loaded camera intrinsics from %s.", intrinsics_path)

            extrinsics_data = np.load(extrinsics_path)
            rotation_vector = extrinsics_data.get("rotation_vector")
            if rotation_vector is None:
                rotation_vector = extrinsics_data.get("rvec")
            translation_vector = extrinsics_data.get("translation_vector")
            if translation_vector is None:
                translation_vector = extrinsics_data.get("tvec")
            logging.info("Loaded camera extrinsics from %s.", extrinsics_path)
        except Exception as e:
            logging.critical("Failed to load calibration data: %s", e)
            sys.exit(1)

        return (
            camera_matrix,
            distortion_coefficients,
            rotation_vector,
            translation_vector,
        )

    def _create_app_context(
        self,
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
        if (
            aruco_detector.camera_matrix is None
            and self.config.camera_matrix is not None
        ):
            aruco_detector.set_calibration(
                self.config.camera_matrix, self.config.distortion_coefficients
            )
        if (
            aruco_detector.rotation_vector is None
            and self.config.rotation_vector is not None
        ):
            aruco_detector.set_extrinsics(
                self.config.rotation_vector, self.config.translation_vector
            )

        # Initialize Camera Projection Model
        camera_projection_model = None
        projection_service = None
        if (
            self.config.camera_matrix is not None
            and self.config.rotation_vector is not None
            and self.config.translation_vector is not None
        ):
            camera_projection_model = CameraProjectionModel(
                camera_matrix=self.config.camera_matrix,
                distortion_coefficients=self.config.distortion_coefficients,
                rotation_vector=self.config.rotation_vector,
                translation_vector=self.config.translation_vector,
            )
            self.config.camera_projection_model = camera_projection_model

            if self.config.projector_3d_model is not None:
                projection_service = ProjectionService(
                    camera_projection_model,
                    self.config.projector_3d_model,
                    ppi=self.config.projector_ppi,
                    distortion_model=self.config.distortion_model,
                )

        return AppContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            notifications=self.notifications,
            visibility_engine=self.visibility_engine,
            aruco_detector=aruco_detector,
            camera_projection_model=camera_projection_model,
            projection_service=projection_service,
            debug_mode=debug_mode,
            show_tokens=show_tokens,
            raw_tokens=self.state.raw_tokens,
            state=self.state,
            analytics=AnalyticsManager(self.config.storage_manager),
            events=self.events,
            time_provider=self.time_provider,
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
                projection_service=self.app_context.projection_service,
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
            SceneId.EXCLUSIVE_VISION: ExclusiveVisionScene(self.app_context),
            SceneId.CALIBRATE_FLASH: FlashCalibrationScene(self.app_context),
            SceneId.CALIBRATE_PPI: PpiCalibrationScene(self.app_context),
            SceneId.CALIBRATE_MAP_GRID: MapGridCalibrationScene(self.app_context),
            SceneId.CALIBRATE_INTRINSICS: IntrinsicsCalibrationScene(self.app_context),
            SceneId.CALIBRATE_PROJECTOR: ProjectorCalibrationScene(self.app_context),
            SceneId.CALIBRATE_EXTRINSICS: ExtrinsicsCalibrationScene(self.app_context),
            SceneId.CALIBRATE_PROJECTOR_3D: Projector3DCalibrationScene(
                self.app_context
            ),
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
        # Always ensure it is set correctly
        self.app_context.debug_mode = enabled

    def reload_config(self, new_config: AppConfig):
        """Reloads application configuration, rebuilding context and scenes."""
        self.config = new_config
        # Ensure latest global settings are reflected
        self.config.sync_from_global_settings(self.map_config.data.global_settings)

        self.renderer = Renderer(new_config, self.config.projector_3d_model)
        self.input_processor = InputProcessor(new_config)

        # Update core systems with new config/resolution
        self.map_system.config = new_config
        self.fow_manager.sync_resolution(new_config.width, new_config.height)

        camera_matrix, distortion_coefficients, rotation_vector, translation_vector = (
            self._load_camera_calibration()
        )

        # Sync calibration back to config
        self.config.camera_matrix = camera_matrix
        self.config.distortion_coefficients = distortion_coefficients
        self.config.rotation_vector = rotation_vector
        self.config.translation_vector = translation_vector

        # Sync calibration to background tracker
        self.tracking_coordinator.token_tracker.set_aruco_calibration(
            camera_matrix, distortion_coefficients, rotation_vector, translation_vector
        )

        self.app_context = self._create_app_context(
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
            self.state._scene_atom.update(self.current_scene.__class__.__name__)
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
        dt = 0.0
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # Update temporal authority
        self.events.advance(dt)

        # Trigger pruning
        self.app_context.notifications.get_active_notifications()

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
                transition = self._handle_payloads(action_data, state)
                if transition:
                    self._switch_scene(transition)
                elif action_name:
                    # If not handled by ActionDispatcher, pass it as a semantic action to the scene
                    if actions is not None:
                        actions.append(action_name)
            state.pending_actions.clear()

        # Standardize Input and Sync Context
        self.input_coordinator.update(state, current_time)

        # Update dwell state if available in current scene
        dwell_tracker = getattr(self.current_scene, "dwell_tracker", None)
        if dwell_tracker:
            state.dwell_state = {
                "accumulated_time": dwell_tracker.accumulated_time,
                "dwell_time_threshold": dwell_tracker.dwell_time_threshold,
                "is_triggered": dwell_tracker.is_triggered,
                "last_point": dwell_tracker.last_point,
                "target_id": dwell_tracker.target_id,  # Use internal tracker's target_id
            }
        else:
            state.dwell_state = {}

        # Update summon progress
        summon_p = 0.0
        import light_map.menu_config as config_vars

        if self.events.has_event(TimerKey.SUMMON_MENU_STEP_1):
            rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU_STEP_1)
            summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_STEP_1_TIME))
        elif self.events.has_event(TimerKey.SUMMON_MENU_STEP_2):
            rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU_STEP_2)
            summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_STEP_2_TIME))
        elif self.events.has_event(TimerKey.SUMMON_MENU):
            # In MapScene, SUMMON_MENU is the actual timer for summoning
            # In ViewingScene, it's just a marker for step 2 window (ignore progress for marker)
            if self.current_scene_name == "MapScene":
                rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU)
                summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_TIME))

        state.summon_progress = summon_p

        # --- VISIBILITY AND LAYER STACK ---
        current_stack = self.get_layer_stack()

        # We need to update tokens in map system from state
        self.map_system.ghost_tokens = state.tokens

        # Scene Update
        transition = self.current_scene.update(state.inputs, actions, current_time)
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
                self.state.map_render_state = MapRenderState(
                    opacity=new_opacity,
                    quality=new_quality,
                    filepath=self.current_map_path,
                )

            # 2. Update SceneLayer bridge
            self.layer_manager.scene_layer.scene = self.current_scene
            # Synchronize last seen scene version
            if self.current_scene.version != self.last_scene_version:
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

        # Final State Updates (AFTER scene and action processing)
        state.update_performance_metrics(self.fps)
        self.current_scene_name = self.current_scene.__class__.__name__
        state.current_scene_name = self.current_scene_name
        state.effective_show_tokens = self.effective_show_tokens

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
                self.state.visibility_mask = combined_pc_mask.copy()

                # 5. Invalidate Layer Caches
                self.state.fow_mask = self.fow_manager.explored_mask.copy()

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
        self.state.grid_metadata = GridMetadata(
            spacing_svg=spacing,
            origin_svg_x=entry.grid_origin_svg_x,
            origin_svg_y=entry.grid_origin_svg_y,
        )

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
        # Ensure visibility mask is updated to trigger re-render if blockers changed
        if self.state.visibility_mask is not None:
            self.state.visibility_mask = self.state.visibility_mask.copy()

    def _handle_payloads(
        self, payload: Any, state: Optional["WorldState"] = None
    ) -> Optional["SceneTransition"]:
        """Handle side-effects from scene transitions, like loading maps."""
        return self.action_dispatcher.dispatch(payload, state)

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
        self.state.map_render_state = MapRenderState(
            opacity=self.layer_manager.map_layer.opacity,
            quality=self.layer_manager.map_layer.quality,
            filepath=filename,
        )

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
            self.state.visibility_mask = self.fow_manager.visible_mask.copy()
            self.state.fow_mask = self.fow_manager.explored_mask.copy()

        if load_session:
            session_dir = None
            if self.config.storage_manager:
                session_dir = os.path.join(
                    self.config.storage_manager.get_data_dir(), "sessions"
                )
            session = SessionManager.load_for_map(filename, session_dir=session_dir)
            if session:
                self.map_system.ghost_tokens = session.tokens
                self.state.tokens = list(session.tokens)

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
