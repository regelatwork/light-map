from enum import StrEnum
from dataclasses import dataclass, field
from typing import List, Optional


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


class AppMode(StrEnum):
    MENU = "MENU"
    MAP = "MAP"
    CALIB_PPI = "CALIB_PPI"
    CALIB_MAP_GRID = "CALIB_MAP_GRID"


@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None  # Leaf if set
    children: List["MenuItem"] = field(default_factory=list)  # Node if set
    should_close_on_trigger: bool = True
    # NOTE: 'toggled' state is NOT stored here. It is immutable config.
