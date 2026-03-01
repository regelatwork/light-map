from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import numpy as np
from light_map.core.storage import StorageManager


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
    PAGE_NEXT = "PAGE_NEXT"
    PAGE_PREV = "PAGE_PREV"
    SCAN_SESSION = "SCAN_SESSION"
    LOAD_SESSION = "LOAD_SESSION"
    CALIBRATE_FLASH = "CALIBRATE_FLASH"
    SCAN_ALGORITHM = "SCAN_ALGORITHM"
    TOGGLE_HAND_MASKING = "TOGGLE_HAND_MASKING"
    SET_GM_POSITION = "SET_GM_POSITION"


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


class ResultType(StrEnum):
    ARUCO = "ARUCO"
    HANDS = "HANDS"
    GESTURE = "GESTURE"


class Action(StrEnum):
    SELECT = "SELECT"
    BACK = "BACK"
    MOVE = "MOVE"


@dataclass
class DetectionResult:
    timestamp: int
    type: ResultType
    data: Any


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
    projector_matrix_resolution: Tuple[int, int] = (2304, 1296)
    map_search_patterns: List[str] = field(default_factory=list)
    distortion_model: Optional[Any] = None
    storage_manager: Optional[Any] = None
    log_level: str = "INFO"
    log_file: str = _DEFAULT_STORAGE.get_state_path("light_map.log")

    # Masking settings
    enable_hand_masking: bool = False
    hand_mask_padding: int = 30
    hand_mask_blur: int = 15
    gm_position: GmPosition = GmPosition.NONE


@dataclass
class ViewportState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0


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
    confidence: float = 1.0
    is_occluded: bool = False
    is_duplicate: bool = False


@dataclass
class SessionData:
    map_file: str
    viewport: ViewportState
    tokens: List[Token]
    timestamp: str = ""


@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None  # Leaf if set
    children: List["MenuItem"] = field(default_factory=list)  # Node if set
    should_close_on_trigger: bool = True
    # NOTE: 'toggled' state is NOT stored here. It is immutable config.
