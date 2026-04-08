from __future__ import annotations

# NOTE: Many enums in this file are mirrored in frontend/src/types/system.ts
# Changes here MUST be kept in sync with the frontend.
# This is enforced by tests/test_enum_sync.py.
from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict, TYPE_CHECKING
from abc import ABC, abstractmethod

import numpy as np
from light_map.core.storage import StorageManager
from .constants import (
    DEFAULT_PROJECTOR_RESOLUTION,
    DEFAULT_HAND_MASK_PADDING,
    DEFAULT_PROJECTOR_PPI,
    DEFAULT_POINTER_EXTENSION_INCHES,
    DEFAULT_INSPECTION_LINGER_DURATION,
    DEFAULT_DOOR_THICKNESS_MULTIPLIER,
    DEFAULT_ARUCO_MASK_PADDING,
)

if TYPE_CHECKING:
    from light_map.core.world_state import WorldState
    from .vision.projection import Projector3DModel, CameraProjectionModel


class LayerMode(StrEnum):
    NORMAL = "NORMAL"
    BLOCKING = "BLOCKING"


@dataclass
class ImagePatch:
    """Represents a rectangular region of pixels to be composited."""

    x: int
    y: int
    width: int
    height: int
    data: np.ndarray  # BGRA


@dataclass
class CalibrationState:
    """Stores transient state for calibration scenes to avoid manual version bumps."""

    stage: str = ""
    target_status: List[str] = field(default_factory=list)
    target_info: List[Dict[str, Any]] = field(default_factory=list)
    reprojection_error: float = 0.0
    animation_start_times: Dict[int, float] = field(default_factory=dict)
    last_camera_frame_ts: int = 0
    captured_count: int = 0
    total_required: int = 0
    candidate_ppi: float = 0.0
    step_index: int = 0


class Layer(ABC):
    """
    Abstract Base Class for all visual layers.
    Uses strictly monotonic versions for efficient caching and re-rendering.
    """

    def __init__(
        self,
        state: Optional["WorldState"] = None,
        is_static: bool = False,
        layer_mode: LayerMode = LayerMode.NORMAL,
    ):
        self.state = state
        self.is_static = is_static
        self.layer_mode = layer_mode
        self._cached_patches: Optional[List[ImagePatch]] = None
        self._last_rendered_version: int = -1  # Consumer-side version tracking

    @abstractmethod
    def get_current_version(self) -> int:
        """
        Returns the logical version of the layer based on its dependencies.
        Subclasses should combine relevant timestamps from self.state.
        """
        pass

    def render(self, current_time: float = 0.0) -> Tuple[List[ImagePatch], int]:
        """
        Handles caching and calls _generate_patches if any dependency version changed.
        Returns the cached or newly generated patches and the version they satisfy.
        """
        current_version = self.get_current_version()

        if (
            current_version != self._last_rendered_version
            or self._cached_patches is None
        ):
            self._cached_patches = self._generate_patches(current_time)
            self._last_rendered_version = current_version

        return self._cached_patches, self._last_rendered_version

    @abstractmethod
    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        """Actual rendering logic implemented by subclasses."""
        pass


class CompositeLayer(Layer):
    """
    Groups multiple internal layers and flattens their output into a single cached patch.
    This optimizes rendering by treating a sub-stack of layers as one unit.
    """

    def __init__(self, layers: List[Layer], is_static: bool = True):
        super().__init__(state=None, is_static=is_static, layer_mode=LayerMode.NORMAL)
        self.layers = layers

    def get_current_version(self) -> int:
        """The version is a combination (sum) of all internal layers' versions."""
        total_version = 0
        for layer in self.layers:
            total_version += layer.get_current_version()
        return total_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.layers:
            return []

        all_layer_patches = []
        for layer in self.layers:
            patches, _ = layer.render(current_time)
            if patches:
                all_layer_patches.extend(patches)

        if not all_layer_patches:
            return []

        # Find the bounding box of all patches to optimize buffer size
        min_x = min(p.x for p in all_layer_patches)
        min_y = min(p.y for p in all_layer_patches)
        max_x = max(p.x + p.width for p in all_layer_patches)
        max_y = max(p.y + p.height for p in all_layer_patches)

        w = max_x - min_x
        h = max_y - min_y

        if w <= 0 or h <= 0:
            return []

        buffer = np.zeros((h, w, 4), dtype=np.uint8)

        # Composite patches onto the local buffer
        for p in all_layer_patches:
            px1, py1 = max(0, p.x - min_x), max(0, p.y - min_y)
            px2, py2 = min(w, p.x - min_x + p.width), min(h, p.y - min_y + p.height)

            if px1 >= px2 or py1 >= py2:
                continue

            src_x1, src_y1 = px1 - (p.x - min_x), py1 - (p.y - min_y)
            src_x2, src_y2 = src_x1 + (px2 - px1), src_y1 + (py2 - py1)

            patch_slice = p.data[src_y1:src_y2, src_x1:src_x2]

            if p.data.shape[2] == 4:
                # Alpha composite
                alpha_channel = patch_slice[:, :, 3]
                if not np.any(alpha_channel):
                    continue

                alpha = alpha_channel[:, :, np.newaxis].astype(np.uint16)
                roi = buffer[py1:py2, px1:px2].astype(np.uint16)
                src_bgr = patch_slice[:, :, :3].astype(np.uint16)

                blended_bgr = (src_bgr * alpha + roi[:, :, :3] * (255 - alpha)) // 255

                # Composite alpha (simplified)
                dst_alpha = roi[:, :, 3]
                blended_alpha = (
                    alpha_channel.astype(np.uint16)
                    + dst_alpha * (255 - alpha_channel.astype(np.uint16)) // 255
                )

                buffer[py1:py2, px1:px2, :3] = blended_bgr.astype(np.uint8)
                buffer[py1:py2, px1:px2, 3] = blended_alpha.astype(np.uint8)
            else:
                # Opaque block
                buffer[py1:py2, px1:px2, :3] = patch_slice[:, :, :3]
                buffer[py1:py2, px1:px2, 3] = 255

        return [ImagePatch(x=min_x, y=min_y, width=w, height=h, data=buffer)]


class GestureType(StrEnum):
    OPEN_PALM = "Open Palm"
    CLOSED_FIST = "Closed Fist"
    GUN = "Gun"
    POINTING = "Pointing"
    VICTORY = "Victory"
    ROCK = "Rock"
    SHAKA = "Shaka"
    UNKNOWN = "Unknown"
    NONE = "None"


class TokenMergePolicy(StrEnum):
    PHYSICAL_PRIORITY = "PHYSICAL_PRIORITY"
    REMOTE_PRIORITY = "REMOTE_PRIORITY"
    PHYSICAL_ONLY = "PHYSICAL_ONLY"
    REMOTE_ONLY = "REMOTE_ONLY"


class TokenDetectionAlgorithm(StrEnum):
    FLASH = "FLASH"
    STRUCTURED_LIGHT = "STRUCTURED_LIGHT"
    ARUCO = "ARUCO"


class NamingStyle(StrEnum):
    NUMBERED = "NUMBERED"
    AMERICAN = "AMERICAN"
    SCI_FI = "SCI_FI"
    FANTASY = "FANTASY"


class MenuActions(StrEnum):
    TOGGLE_DEBUG_MODE = "TOGGLE_DEBUG_MODE"
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    EXIT = "EXIT"
    CLOSE_MENU = "CLOSE_MENU"
    CALIBRATE = "CALIBRATE"
    CALIBRATE_INTRINSICS = "CALIBRATE_INTRINSICS"
    CALIBRATE_PROJECTOR = "CALIBRATE_PROJECTOR"
    CALIBRATE_PPI = "CALIBRATE_PPI"
    CALIBRATE_EXTRINSICS = "CALIBRATE_EXTRINSICS"
    CALIBRATE_PROJECTOR_3D = "CALIBRATE_PROJECTOR_3D"
    NAV_BACK = "NAV_BACK"
    MAP_CONTROLS = "MAP_CONTROLS"
    ROTATE_CW = "ROTATE_CW"
    ROTATE_CCW = "ROTATE_CCW"
    RESET_VIEW = "RESET_VIEW"
    CALIBRATE_SCALE = "CALIBRATE_SCALE"
    SET_MAP_SCALE = "SET_MAP_SCALE"
    RESET_ZOOM = "RESET_ZOOM"
    UNDO_NAV = "UNDO_NAV"
    REDO_NAV = "REDO_NAV"
    PAGE_NEXT = "PAGE_NEXT"
    PAGE_PREV = "PAGE_PREV"
    SCAN_SESSION = "SCAN_SESSION"
    LOAD_SESSION = "LOAD_SESSION"
    CALIBRATE_FLASH = "CALIBRATE_FLASH"
    SCAN_ALGORITHM = "SCAN_ALGORITHM"
    TOGGLE_HAND_MASKING = "TOGGLE_HAND_MASKING"
    TOGGLE_ARUCO_MASKING = "TOGGLE_ARUCO_MASKING"
    SET_GM_POSITION = "SET_GM_POSITION"
    SYNC_VISION = "SYNC_VISION"
    RESET_FOW = "RESET_FOW"
    TOGGLE_FOW = "TOGGLE_FOW"
    TOGGLE_DOOR = "TOGGLE_DOOR"
    TOGGLE_TOKENS = "TOGGLE_TOKENS"


class SceneId(StrEnum):
    MENU = "MENU"
    VIEWING = "VIEWING"
    MAP = "MAP"
    SCANNING = "SCANNING"
    CALIBRATE_FLASH = "CALIBRATE_FLASH"
    CALIBRATE_PPI = "CALIBRATE_PPI"
    CALIBRATE_MAP_GRID = "CALIBRATE_MAP_GRID"
    CALIBRATE_INTRINSICS = "CALIBRATE_INTRINSICS"
    CALIBRATE_PROJECTOR = "CALIBRATE_PROJECTOR"
    CALIBRATE_EXTRINSICS = "CALIBRATE_EXTRINSICS"
    CALIBRATE_PROJECTOR_3D = "CALIBRATE_PROJECTOR_3D"
    EXCLUSIVE_VISION = "EXCLUSIVE_VISION"


class SelectionType(StrEnum):
    NONE = "NONE"
    DOOR = "DOOR"
    TOKEN = "TOKEN"


class TimerKey(StrEnum):
    INSPECTION_LINGER = "inspection_linger"
    SUMMON_MENU = "summon_menu"
    SUMMON_MENU_STEP_1 = "summon_menu_step_1"
    SUMMON_MENU_STEP_2 = "summon_menu_step_2"
    DWELL = "dwell"
    SCANNING_STAGE = "scanning_stage"
    CALIBRATION_STAGE = "calibration_stage"
    NOTIFICATION_EXPIRY = "notification_expiry"
    GESTURE_TIMEOUT = "gesture_timeout"


@dataclass(frozen=True)
class MapRenderState:
    """Encapsulates the rendering configuration for the map layer."""

    opacity: float = 1.0
    quality: int = 100
    filepath: str = ""


@dataclass
class SelectionState:
    type: SelectionType = SelectionType.NONE
    id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GridMetadata:
    spacing_svg: float = 0.0
    origin_svg_x: float = 0.0
    origin_svg_y: float = 0.0


class ResultType(StrEnum):
    ARUCO = "ARUCO"
    HANDS = "HANDS"
    GESTURE = "GESTURE"
    ACTION = "ACTION"


class Action(StrEnum):
    SELECT = "SELECT"
    BACK = "BACK"
    MOVE = "MOVE"
    QUIT = "QUIT"
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    # Action triggers from temporal events or complex logic
    TRIGGER_MENU = "TRIGGER_MENU"
    TOGGLE_TOKEN_VISIBILITY = "TOGGLE_TOKEN_VISIBILITY"
    CLEAR_INSPECTION = "CLEAR_INSPECTION"
    DWELL_TRIGGER = "DWELL_TRIGGER"


@dataclass
class DetectionResult:
    timestamp: int
    type: ResultType
    data: Any
    metadata: Dict[str, int] = field(default_factory=dict)


class GmPosition(StrEnum):
    NONE = "None"
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    NORTH_WEST = "North West"
    NORTH_EAST = "North East"
    SOUTH_WEST = "South West"
    SOUTH_EAST = "South East"


_DEFAULT_STORAGE = StorageManager()


@dataclass(frozen=True)
class ProjectorPose:
    """Represents the absolute 3D position of the projector in world coordinates (mm)."""

    x: float
    y: float
    z: float

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]


@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    projector_matrix_resolution: Tuple[int, int] = DEFAULT_PROJECTOR_RESOLUTION
    camera_resolution: Tuple[int, int] = (0, 0)  # Runtime camera resolution
    camera_matrix: Optional[np.ndarray] = None
    distortion_coefficients: Optional[np.ndarray] = None
    rotation_vector: Optional[np.ndarray] = None
    translation_vector: Optional[np.ndarray] = None
    map_search_patterns: List[str] = field(default_factory=list)
    distortion_model: Optional[Any] = None
    storage_manager: Optional[Any] = None
    projector_3d_model: Optional[Projector3DModel] = None
    camera_projection_model: Optional[CameraProjectionModel] = None
    log_level: str = "INFO"
    log_file: str = _DEFAULT_STORAGE.get_state_path("light_map.log")

    # Masking settings
    enable_hand_masking: bool = False
    hand_mask_padding: int = DEFAULT_HAND_MASK_PADDING
    enable_aruco_masking: bool = True
    aruco_mask_padding: int = DEFAULT_ARUCO_MASK_PADDING
    gm_position: GmPosition = GmPosition.NONE
    projector_ppi: float = DEFAULT_PROJECTOR_PPI
    calibration_box_height_mm: float = 78.0
    calibration_box_width_mm: float = 188.0
    calibration_box_length_mm: float = 295.0
    use_projector_3d_model: bool = True
    
    # Manual Projector Position Overrides
    projector_pos_x_override: Optional[float] = None
    projector_pos_y_override: Optional[float] = None
    projector_pos_z_override: Optional[float] = None

    aruco_defaults: Dict[int, Any] = field(default_factory=dict)
    token_profiles: Dict[str, Any] = field(default_factory=dict)
    pointer_extension_inches: float = DEFAULT_POINTER_EXTENSION_INCHES
    inspection_linger_duration: float = DEFAULT_INSPECTION_LINGER_DURATION
    door_thickness_multiplier: float = DEFAULT_DOOR_THICKNESS_MULTIPLIER

    def sync_from_global_settings(self, gs: Any):
        """Syncs config fields from GlobalMapConfig object while avoiding circular imports."""
        self.enable_hand_masking = getattr(
            gs, "enable_hand_masking", self.enable_hand_masking
        )
        self.hand_mask_padding = getattr(
            gs, "hand_mask_padding", self.hand_mask_padding
        )
        self.enable_aruco_masking = getattr(
            gs, "enable_aruco_masking", self.enable_aruco_masking
        )
        self.aruco_mask_padding = getattr(
            gs, "aruco_mask_padding", self.aruco_mask_padding
        )
        self.gm_position = getattr(gs, "gm_position", self.gm_position)
        self.projector_ppi = getattr(gs, "projector_ppi", self.projector_ppi)
        self.calibration_box_height_mm = getattr(
            gs, "calibration_box_height_mm", self.calibration_box_height_mm
        )
        self.calibration_box_width_mm = getattr(
            gs, "calibration_box_width_mm", self.calibration_box_width_mm
        )
        self.calibration_box_length_mm = getattr(
            gs, "calibration_box_length_mm", self.calibration_box_length_mm
        )
        self.use_projector_3d_model = getattr(
            gs, "use_projector_3d_model", self.use_projector_3d_model
        )
        
        # Sync Projector Position Overrides
        self.projector_pos_x_override = getattr(
            gs, "projector_pos_x_override", self.projector_pos_x_override
        )
        self.projector_pos_y_override = getattr(
            gs, "projector_pos_y_override", self.projector_pos_y_override
        )
        self.projector_pos_z_override = getattr(
            gs, "projector_pos_z_override", self.projector_pos_z_override
        )

        self.aruco_defaults = getattr(gs, "aruco_defaults", self.aruco_defaults)
        self.token_profiles = getattr(gs, "token_profiles", self.token_profiles)
        self.inspection_linger_duration = getattr(
            gs, "inspection_linger_duration", self.inspection_linger_duration
        )
        self.door_thickness_multiplier = getattr(
            gs, "door_thickness_multiplier", self.door_thickness_multiplier
        )


@dataclass
class ViewportState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "zoom": self.zoom,
            "rotation": self.rotation,
        }


@dataclass
class Token:
    id: int
    world_x: float  # SVG coordinates (Vertical projection to Z=0)
    world_y: float
    world_z: float = 0.0  # Height of the base on the map (typically 0.0)
    marker_x: Optional[float] = (
        None  # SVG coordinates of the physical marker (at height Z=h)
    )
    marker_y: Optional[float] = None
    marker_z: float = 0.0  # Height of the marker in mm (h)
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    screen_x: Optional[float] = None
    screen_y: Optional[float] = None
    confidence: float = 1.0
    is_occluded: bool = False
    is_duplicate: bool = False
    name: Optional[str] = None
    color: Optional[str] = None
    type: str = "NPC"
    profile: Optional[str] = None
    size: Optional[int] = None
    height_mm: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "world_x": self.world_x,
            "world_y": self.world_y,
            "world_z": self.world_z,
            "marker_x": self.marker_x,
            "marker_y": self.marker_y,
            "marker_z": self.marker_z,
            "grid_x": self.grid_x,
            "grid_y": self.grid_y,
            "screen_x": self.screen_x,
            "screen_y": self.screen_y,
            "confidence": self.confidence,
            "is_occluded": self.is_occluded,
            "is_duplicate": self.is_duplicate,
            "name": self.name,
            "color": self.color,
            "type": self.type,
            "profile": self.profile,
            "size": self.size,
            "height_mm": self.height_mm,
        }


@dataclass
class SessionData:
    map_file: str
    viewport: ViewportState
    tokens: List[Token]
    door_states: Dict[str, bool] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None  # Leaf if set
    children: List["MenuItem"] = field(default_factory=list)  # Node if set
    should_close_on_trigger: bool = True
    # NOTE: 'toggled' state is NOT stored here. It is immutable config.
