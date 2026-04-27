from __future__ import annotations
import numpy as np
import time
import os
import sys
import logging
from typing import List, Tuple, Any, Dict, Optional, TYPE_CHECKING, Callable

from light_map.core.common_types import (
    AppConfig,
    Layer,
    SceneId,
    TimerKey,
    MapRenderState,
)
from light_map.rendering.renderer import Renderer
from light_map.map.map_system import MapSystem
from light_map.map.map_config import MapConfigManager
from light_map.visibility.fow_manager import FogOfWarManager
from light_map.visibility.visibility_engine import VisibilityEngine

from light_map.core.analytics import AnalyticsManager
from light_map.core.notification import NotificationManager
from light_map.core.layer_stack_manager import LayerStackManager
from light_map.core.scene import Scene
from light_map.core.scene_manager import SceneManager


from light_map.vision.infrastructure.tracking_coordinator import TrackingCoordinator
from light_map.vision.processing.input_processor import InputProcessor
from light_map.vision.detectors.aruco_detector import ArucoTokenDetector
from light_map.vision.environment_manager import EnvironmentManager
from light_map.rendering.projection import (
    Projector3DModel,
    CameraProjectionModel,
    ProjectionService,
)

from light_map.state.world_state import WorldState

if TYPE_CHECKING:
    from light_map.core.common_types import Action, Token
    from light_map.core.scene import SceneTransition
    from light_map.core.app_context import MainContext


from light_map.state.temporal_event_manager import TemporalEventManager
from light_map.action_dispatcher import ActionDispatcher
from light_map.input.input_coordinator import InputCoordinator

# Re-added for backward compatibility with tests
from light_map.menu.menu_scene import MenuScene
from light_map.map.map_scene import MapScene, ViewingScene
from light_map.vision.scanning_scene import ScanningScene
from light_map.visibility.exclusive_vision_scene import ExclusiveVisionScene
from light_map.calibration.calibration_scenes import (
    FlashCalibrationScene,
    PpiCalibrationScene,
    MapGridCalibrationScene,
    IntrinsicsCalibrationScene,
    ProjectorCalibrationScene,
    ExtrinsicsCalibrationScene,
    Projector3DCalibrationScene,
)


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

        # State management
        self.state = WorldState()
        self.events.state = self.state

        # Core Systems (to be replaced by PersistenceService eventually)
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

        # Visibility and FoW Systems - Temporary engines until map is loaded
        self.visibility_engine = VisibilityEngine(grid_spacing_svg=10.0)
        self.fow_manager = FogOfWarManager(config.width, config.height)
        self.current_map_path: Optional[str] = None

        # New Modular Coordinators
        self.tracking_coordinator = TrackingCoordinator(time_provider)
        self.input_processor = InputProcessor(config)

        # Performance Tracking
        from light_map.core.analytics import LatencyInstrument

        self.instrument = LatencyInstrument()

        # Load and Normalize Calibration
        self._initialize_calibration()

        # Scan for maps if provided
        if config.map_search_patterns:
            self.map_config.scan_for_maps(config.map_search_patterns)

        # Initialize Managers and Contexts
        from light_map.persistence.persistence_service import PersistenceService
        from light_map.core.scene_manager import SceneManager

        # AppContext (shared state for scenes)
        self.app_context = self._create_main_context()

        # Initialize Specialized Managers
        self.persistence_service = PersistenceService(self)
        self.environment_manager = EnvironmentManager(self.app_context, self.state)

        # Build scene class map using local names (to support test patching)
        scene_classes = {
            SceneId.MENU: MenuScene,
            SceneId.VIEWING: ViewingScene,
            SceneId.MAP: MapScene,
            SceneId.SCANNING: ScanningScene,
            SceneId.EXCLUSIVE_VISION: ExclusiveVisionScene,
            SceneId.CALIBRATE_FLASH: FlashCalibrationScene,
            SceneId.CALIBRATE_PPI: PpiCalibrationScene,
            SceneId.CALIBRATE_MAP_GRID: MapGridCalibrationScene,
            SceneId.CALIBRATE_INTRINSICS: IntrinsicsCalibrationScene,
            SceneId.CALIBRATE_PROJECTOR: ProjectorCalibrationScene,
            SceneId.CALIBRATE_EXTRINSICS: ExtrinsicsCalibrationScene,
            SceneId.CALIBRATE_PROJECTOR_3D: Projector3DCalibrationScene,
        }
        self.scene_manager = SceneManager(
            self.app_context, self.state, scene_classes=scene_classes
        )

        # Layer Management
        self.layer_manager = LayerStackManager(self.app_context, self.state)
        self.app_context.layer_manager = self.layer_manager

        # Update environment manager with everything needed
        self.environment_manager.fow_manager = self.fow_manager

        # Action and Input Handling
        self.action_dispatcher = ActionDispatcher(self)
        self.input_coordinator = InputCoordinator(self)

        # Final setup
        self._initialize_projector_pose()
        self.state.current_scene_name = self.current_scene_name
        self.state.update_performance_metrics(0.0)
        self.current_scene.on_enter()

    def _initialize_calibration(self):
        """Loads and normalizes camera calibration, syncing to config and trackers."""
        camera_matrix, distortion_coefficients, rotation_vector, translation_vector = (
            self._load_camera_calibration()
        )

        camera_matrix, rotation_vector, translation_vector = (
            self._normalize_calibration(
                camera_matrix, rotation_vector, translation_vector
            )
        )

        self.config.camera_matrix = camera_matrix
        self.config.distortion_coefficients = distortion_coefficients
        self.config.rotation_vector = rotation_vector
        self.config.translation_vector = translation_vector

        self.tracking_coordinator.token_tracker.set_aruco_calibration(
            camera_matrix, distortion_coefficients, rotation_vector, translation_vector
        )

    def _initialize_projector_pose(self):
        """Sets the initial projector pose in the WorldState."""
        calibrated_pos = self.config.projector_3d_model.calibrated_projector_center
        if calibrated_pos is not None:
            from light_map.core.common_types import ProjectorPose

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

    def _create_main_context(self) -> MainContext:
        """Creates the full MainContext for the application."""
        from light_map.core.app_context import MainContext

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

        return MainContext(
            app_config=self.config,
            renderer=self.renderer,
            map_system=self.map_system,
            map_config_manager=self.map_config,
            notifications=self.notifications,
            visibility_engine=self.visibility_engine,
            aruco_detector=aruco_detector,
            camera_projection_model=camera_projection_model,
            projection_service=projection_service,
            debug_mode=False,
            show_tokens=True,
            raw_tokens=self.state.raw_tokens,
            state=self.state,
            analytics=AnalyticsManager(self.config.storage_manager),
            events=self.events,
            time_provider=self.time_provider,
            save_session=self.save_session,
        )

    @property
    def fow_manager(self) -> FogOfWarManager:
        if hasattr(self, "environment_manager") and self.environment_manager:
            mgr = self.environment_manager.fow_manager
            if mgr is not None:
                return mgr
        return getattr(self, "_fow_manager", None)

    @fow_manager.setter
    def fow_manager(self, value: FogOfWarManager):
        self._fow_manager = value
        if hasattr(self, "environment_manager") and self.environment_manager:
            self.environment_manager.fow_manager = value

    @property
    def visibility_engine(self) -> VisibilityEngine:
        if hasattr(self, "environment_manager") and self.environment_manager:
            mgr = self.environment_manager.visibility_engine
            if mgr is not None:
                return mgr
        return getattr(self, "_visibility_engine", None)

    @visibility_engine.setter
    def visibility_engine(self, value: VisibilityEngine):
        self._visibility_engine = value
        if hasattr(self, "environment_manager") and self.environment_manager:
            self.environment_manager.visibility_engine = value
        if hasattr(self, "app_context") and self.app_context:
            self.app_context.visibility_engine = value

    @property
    def current_scene(self) -> Scene:
        return self.scene_manager.current_scene

    @current_scene.setter
    def current_scene(self, value: Scene):
        self.scene_manager.current_scene = value

    @property
    def current_scene_id(self) -> SceneId:
        return self.scene_manager.current_scene_id

    @property
    def current_scene_name(self) -> str:
        return self.current_scene.__class__.__name__

    @current_scene_name.setter
    def current_scene_name(self, value: str):
        # Legacy support for tests that want to force a scene name
        # We don't actually change the scene class, just the name reported by state
        # if they really want to mock it.
        self.state.current_scene_name = value

    @property
    def scenes(self) -> Dict[SceneId, Scene]:
        return self.scene_manager.scenes

    def get_layer_stack(self) -> List[Layer]:
        return self.scene_manager.get_layer_stack()

    # Delegate properties to layer_manager for backward compatibility
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

    def process_state(
        self, state: Optional["WorldState"] = None, actions: List["Action"] = None
    ) -> Tuple[Optional[np.ndarray], List[str]]:
        from light_map.core.analytics import track_wait

        self.instrument.log_and_reset_if_needed(interval_s=1.0, level=logging.INFO)

        if state is None:
            state = self.state
        if actions is None:
            actions = []

        if state is not self.state:
            self.state = state
            self.layer_manager.update_state(state)

        current_time = self.time_provider()
        dt = 0.0
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        self.events.advance(dt)
        self.app_context.notifications.get_active_notifications()
        state.update_viewport(self.map_system.state.to_viewport())

        # Update token screen coordinates
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
                    actions.append(action_name)
            state.pending_actions.clear()

        self.input_coordinator.update(state, current_time)
        self._update_dwell_state(state)
        self._update_summon_progress(state)

        # Scene and Visibility logic
        current_stack = self.get_layer_stack()
        self.map_system.ghost_tokens = state.tokens

        transition = self.current_scene.update(state.inputs, actions, current_time)
        if transition:
            self._handle_payloads(transition.payload, state)
            self._switch_scene(transition)

        # Dashboard Tactical View logic: Calculate cover for the selected token
        # if we aren't already in ExclusiveVisionScene (which handles its own).
        if self.current_scene_id != SceneId.EXCLUSIVE_VISION:
            self._update_tactical_bonuses(state)

        state.update_menu_state(getattr(self.current_scene, "menu_state", None))

        # Render logic
        with track_wait("total_render_logic", self.instrument):
            self._sync_map_render_params()
            with track_wait("renderer_composite", self.instrument):
                final_frame = self.renderer.render(
                    state, current_stack, current_time, self.instrument
                )

        state.update_performance_metrics(self.fps)
        state.current_scene_name = self.current_scene_name
        state.effective_show_tokens = self.effective_show_tokens
        return final_frame, []

    def _update_dwell_state(self, state: WorldState):
        dwell_tracker = getattr(self.current_scene, "dwell_tracker", None)
        if dwell_tracker:
            state.dwell_state = {
                "accumulated_time": dwell_tracker.accumulated_time,
                "dwell_time_threshold": dwell_tracker.dwell_time_threshold,
                "is_triggered": dwell_tracker.is_triggered,
                "last_point": dwell_tracker.last_point,
                "target_id": dwell_tracker.target_id,
            }
        else:
            state.dwell_state = {}

    def _update_summon_progress(self, state: WorldState):
        summon_p = 0.0
        import light_map.menu.menu_config as config_vars

        if self.events.has_event(TimerKey.SUMMON_MENU_STEP_1):
            rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU_STEP_1)
            summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_STEP_1_TIME))
        elif self.events.has_event(TimerKey.SUMMON_MENU_STEP_2):
            rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU_STEP_2)
            summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_STEP_2_TIME))
        elif self.events.has_event(TimerKey.SUMMON_MENU):
            if self.current_scene_name == "MapScene":
                rem = self.events.get_remaining_time(TimerKey.SUMMON_MENU)
                summon_p = max(0.0, 1.0 - (rem / config_vars.SUMMON_TIME))
        state.summon_progress = summon_p

    def _sync_map_render_params(self):
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

    def _switch_scene(self, transition: SceneTransition):
        self.scene_manager.handle_transition(transition)

    def _sync_vision(self, state: "WorldState"):
        self.environment_manager.sync_vision(state)

    def _rebuild_visibility_stack(self, entry: Any):
        self.environment_manager.rebuild_visibility_stack(
            entry, self.current_map_path, self.scene_manager.scenes
        )

    def _sync_blockers_to_state(self, state: Optional["WorldState"] = None):
        self.environment_manager.sync_blockers_to_state(state)

    def _handle_payloads(
        self, payload: Any, state: Optional["WorldState"] = None
    ) -> Optional["SceneTransition"]:
        return self.action_dispatcher.dispatch(payload, state)

    def load_map(self, filename: str, load_session: bool = False):
        self.persistence_service.load_map(filename, load_session)

    def save_session(self):
        self.persistence_service.save_session()

    def reload_config(self, new_config: AppConfig):
        """Reloads application configuration, rebuilding context and scenes."""
        self.config = new_config
        self.config.sync_from_global_settings(self.map_config.data.global_settings)
        self.renderer = Renderer(new_config, self.config.projector_3d_model)
        self.input_processor = InputProcessor(new_config)
        self.map_system.config = new_config
        self.fow_manager.sync_resolution(new_config.width, new_config.height)
        self._initialize_calibration()
        self.app_context = self._create_main_context()
        self.persistence_service.state = self.state
        self.environment_manager.context = self.app_context
        self.layer_manager = LayerStackManager(self.app_context, self.state)
        self.app_context.layer_manager = self.layer_manager

        # Build scene class map using local names (to support test patching)
        scene_classes = {
            SceneId.MENU: MenuScene,
            SceneId.VIEWING: ViewingScene,
            SceneId.MAP: MapScene,
            SceneId.SCANNING: ScanningScene,
            SceneId.EXCLUSIVE_VISION: ExclusiveVisionScene,
            SceneId.CALIBRATE_FLASH: FlashCalibrationScene,
            SceneId.CALIBRATE_PPI: PpiCalibrationScene,
            SceneId.CALIBRATE_MAP_GRID: MapGridCalibrationScene,
            SceneId.CALIBRATE_INTRINSICS: IntrinsicsCalibrationScene,
            SceneId.CALIBRATE_PROJECTOR: ProjectorCalibrationScene,
            SceneId.CALIBRATE_EXTRINSICS: ExtrinsicsCalibrationScene,
            SceneId.CALIBRATE_PROJECTOR_3D: Projector3DCalibrationScene,
        }
        self.scene_manager = SceneManager(
            self.app_context, self.state, scene_classes=scene_classes
        )
        self.current_scene.on_enter()
        self.notifications.add_notification("Configuration Reloaded")

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

    def switch_to_viewing(self):
        self.scene_manager.transition_to(SceneId.VIEWING)

    @property
    def aruco_mapper(self) -> Optional[Callable[[Dict[str, Any]], List[Token]]]:
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
            return res

        return mapper

    @property
    def debug_mode(self) -> bool:
        return self.app_context.debug_mode

    @debug_mode.setter
    def debug_mode(self, enabled: bool):
        self.app_context.debug_mode = enabled

    def set_debug_mode(self, enabled: bool):
        self.app_context.debug_mode = enabled

    @property
    def effective_show_tokens(self) -> bool:
        return self.app_context.show_tokens and getattr(
            self.current_scene, "show_tokens", True
        )

    def _load_camera_calibration(
        self,
    ) -> Tuple[
        Optional[np.ndarray],
        Optional[np.ndarray],
        Optional[np.ndarray],
        Optional[np.ndarray],
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

        # Check if we are running in a test environment to avoid sys.exit(1)
        is_testing = "pytest" in sys.modules or "unittest" in sys.modules

        if not os.path.exists(intrinsics_path) or not os.path.exists(extrinsics_path):
            if is_testing:
                logging.warning("Camera Calibration Files Missing (Testing Mode)!")
                return None, None, None, None
            logging.critical("Camera Calibration Files Missing!")
            sys.exit(1)
        try:
            intrinsics_data = np.load(intrinsics_path)
            camera_matrix = intrinsics_data.get("camera_matrix")
            if camera_matrix is None:
                camera_matrix = intrinsics_data.get("mtx")

            distortion_coefficients = intrinsics_data.get("distortion_coefficients")
            if distortion_coefficients is None:
                distortion_coefficients = intrinsics_data.get("dist_coeffs")

            extrinsics_data = np.load(extrinsics_path)
            rotation_vector = extrinsics_data.get("rotation_vector")
            if rotation_vector is None:
                rotation_vector = extrinsics_data.get("rvec")

            translation_vector = extrinsics_data.get("translation_vector")
            if translation_vector is None:
                translation_vector = extrinsics_data.get("tvec")
        except Exception as e:
            if is_testing:
                logging.warning("Failed to load calibration data (Testing Mode): %s", e)
                return None, None, None, None
            logging.critical("Failed to load calibration data: %s", e)
            sys.exit(1)
        return (
            camera_matrix,
            distortion_coefficients,
            rotation_vector,
            translation_vector,
        )

    def _normalize_calibration(
        self,
        camera_matrix: np.ndarray,
        rotation_vector: np.ndarray,
        translation_vector: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        cam_w, cam_h = self.config.camera_resolution
        calib_w, calib_h = self.config.projector_matrix_resolution
        if cam_w == 0 or calib_w == 0 or (cam_w == calib_w and cam_h == calib_h):
            return camera_matrix, rotation_vector, translation_vector
        logging.info(
            f"InteractiveApp: Normalizing calibration from {calib_w}x{calib_h} to {cam_w}x{cam_h}"
        )
        scale_x, scale_y = cam_w / calib_w, cam_h / calib_h
        new_camera_matrix = camera_matrix.copy()
        new_camera_matrix[0, 0] *= scale_x
        new_camera_matrix[0, 2] *= scale_x
        new_camera_matrix[1, 1] *= scale_y
        new_camera_matrix[1, 2] *= scale_y
        inv_scale_x, inv_scale_y = calib_w / cam_w, calib_h / cam_h
        scale_matrix = np.array(
            [[inv_scale_x, 0, 0], [0, inv_scale_y, 0], [0, 0, 1]], dtype=np.float32
        )
        self.config.projector_matrix = self.config.projector_matrix @ scale_matrix
        return new_camera_matrix, rotation_vector, translation_vector

    def _update_tactical_bonuses(self, state: "WorldState"):
        """
        Calculates tactical cover bonuses for the currently selected token.
        This provides the data needed for the GM Dashboard's tactical view.
        """
        from light_map.core.common_types import SelectionType

        if state.selection.type != SelectionType.TOKEN or not state.selection.id:
            if state.tactical_bonuses:
                state.tactical_bonuses = {}
            return

        try:
            attacker_id = int(state.selection.id)
        except (ValueError, TypeError):
            if state.tactical_bonuses:
                state.tactical_bonuses = {}
            return

        # Optimization: Only recalculate if tokens, geometry, or selection changed
        current_version = max(
            state.tokens_version,
            state.visibility_version,
            state.fow_version,
            state.selection_version,
        )

        if (
            hasattr(self, "_last_tactical_calc_version")
            and self._last_tactical_calc_version == current_version
            and hasattr(self, "_last_tactical_attacker_id")
            and self._last_tactical_attacker_id == attacker_id
        ):
            return

        self._last_tactical_calc_version = current_version
        self._last_tactical_attacker_id = attacker_id

        attacker = next((t for t in state.tokens if t.id == attacker_id), None)
        if not attacker:
            state.tactical_bonuses = {}
            return

        # Resolve profiles for size logic
        map_file = self.current_map_path
        attacker_profile = self.map_config.resolve_token_profile(attacker.id, map_file)

        # Check all potential targets
        new_bonuses = {}
        engine = self.visibility_engine
        all_tokens = state.tokens

        for target in all_tokens:
            if target.id == attacker_id:
                continue

            # Basic range check (20 squares)
            dist_sq = (target.world_x - attacker.world_x) ** 2 + (
                target.world_y - attacker.world_y
            ) ** 2
            spacing = engine.grid_spacing_svg
            if dist_sq > (20.0 * spacing) ** 2:
                continue

            target_profile = self.map_config.resolve_token_profile(target.id, map_file)

            # Ensure sizes are correct
            attacker_copy = attacker.copy()
            attacker_copy.size = attacker_profile.size
            target_copy = target.copy()
            target_copy.size = target_profile.size

            # Create augmented mask for soft cover
            augmented_mask = engine.blocker_mask.copy()
            for blocker in all_tokens:
                if blocker.id not in (attacker_id, target.id):
                    engine.stamp_token_footprint(augmented_mask, blocker)

            cover_result = engine.calculate_token_cover_bonuses(
                attacker_copy, target_copy, augmented_mask
            )
            new_bonuses[target.id] = cover_result

        state.tactical_bonuses = new_bonuses
