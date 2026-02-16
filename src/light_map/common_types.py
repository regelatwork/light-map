from enum import StrEnum
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


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


class MenuActions(StrEnum):
    TOGGLE_DEBUG_MODE = "TOGGLE_DEBUG_MODE"
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    EXIT = "EXIT"
    CLOSE_MENU = "CLOSE_MENU"
    CALIBRATE = "CALIBRATE"
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


@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    map_search_patterns: List[str] = field(default_factory=list)


@dataclass
class ViewportState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0


@dataclass
class Token:
    id: int
    world_x: float  # SVG coordinates
    world_y: float
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    confidence: float = 1.0


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
