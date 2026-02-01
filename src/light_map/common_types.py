from enum import StrEnum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

class GestureType(StrEnum):
    OPEN_PALM = "Open Palm"
    CLOSED_FIST = "Closed Fist"
    GUN = "Gun"
    POINTING = "Pointing"
    VICTORY = "Victory"
    ROCK = "Rock"
    SHAKA = "Shaka"
    UNKNOWN = "Unknown"

class MenuActions(StrEnum):
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    EXIT = "EXIT"
    CALIBRATE = "CALIBRATE"
    NAV_BACK = "NAV_BACK"

@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None  # Leaf if set
    children: List['MenuItem'] = field(default_factory=list) # Node if set
    should_close_on_trigger: bool = True
    # NOTE: 'toggled' state is NOT stored here. It is immutable config.
