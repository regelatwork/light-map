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


class Layer(ABC):
    """Abstract Base Class for all visual layers."""

    def __init__(
        self,
        state: Optional[WorldState] = None,
        is_static: bool = False,
        layer_mode: LayerMode = LayerMode.NORMAL,
    ):
        self.state = state
        self.is_static = is_static
        self.layer_mode = layer_mode
        self._cached_patches: Optional[List[ImagePatch]] = None
        self._last_rendered_version: int = -1
        self._is_dynamic: bool = False

    @abstractmethod
    def get_current_version(self) -> int:
        """Returns the logical version of the layer based on its dependencies."""
        pass

    def render(self, current_time: float = 0.0) -> Tuple[List[ImagePatch], int]:
        """Handles caching and calls _generate_patches if version changed."""
        current_version = self.get_current_version()

        if (
            self._is_dynamic
            or current_version != self._last_rendered_version
            or self._cached_patches is None
        ):
            self._cached_patches = self._generate_patches(current_time)
            self._last_rendered_version = current_version

        return self._cached_patches, self._last_rendered_version

    @abstractmethod
    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        """Actual rendering logic implemented by subclasses."""
        pass


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


class SelectionType(StrEnum):
    NONE = "NONE"
    DOOR = "DOOR"
    TOKEN = "TOKEN"


class TimerKey(StrEnum):
    INSPECTION_LINGER = "inspection_linger"
    TOKEN_TOGGLE_COOLDOWN = "token_toggle_cooldown"
    SUMMON_MENU = "summon_menu"
    DWELL = "dwell"


@dataclass
class SelectionState:
    type: SelectionType = SelectionType.NONE
    id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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


@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    projector_matrix_resolution: Tuple[int, int] = DEFAULT_PROJECTOR_RESOLUTION
    camera_resolution: Tuple[int, int] = (0, 0)  # Runtime camera resolution
    camera_matrix: Optional[np.ndarray] = None
    rvec: Optional[np.ndarray] = None
    tvec: Optional[np.ndarray] = None
    map_search_patterns: List[str] = field(default_factory=list)
    distortion_model: Optional[Any] = None
    storage_manager: Optional[Any] = None
    log_level: str = "INFO"
    log_file: str = _DEFAULT_STORAGE.get_state_path("light_map.log")

    # Masking settings
    enable_hand_masking: bool = False
    hand_mask_padding: int = DEFAULT_HAND_MASK_PADDING
    enable_aruco_masking: bool = True
    aruco_mask_padding: int = DEFAULT_ARUCO_MASK_PADDING
    gm_position: GmPosition = GmPosition.NONE
    projector_ppi: float = DEFAULT_PROJECTOR_PPI
    aruco_defaults: Dict[int, Any] = field(default_factory=dict)
    token_profiles: Dict[str, Any] = field(default_factory=dict)
    pointer_extension_inches: float = DEFAULT_POINTER_EXTENSION_INCHES
    inspection_linger_duration: float = DEFAULT_INSPECTION_LINGER_DURATION
    door_thickness_multiplier: float = DEFAULT_DOOR_THICKNESS_MULTIPLIER


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
