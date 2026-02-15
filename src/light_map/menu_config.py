from typing import Tuple
from dataclasses import dataclass
from light_map.common_types import GestureType

# --- Constants ---
LOCK_DELAY: float = 0.3  # Seconds to pin cursor history
GRACE_PERIOD: float = 0.2  # Seconds to wait before resetting prime if gesture is lost
PRIMING_TIME: float = 0.8  # Seconds to hold gesture to trigger action
SUMMON_TIME: float = 1.0  # Seconds to hold summon gesture to open menu
ZOOM_DELAY: float = 0.5  # Seconds to hold two-hand pointing to enter zoom mode
MODE_TRANSITION_DELAY: float = (
    0.5  # Seconds to wait after mode switch before processing input
)

ITEM_WIDTH_PCT: float = 0.6  # Width of menu items relative to screen width
MAX_VISIBLE_ITEMS: int = 8  # Maximum number of items to show at once
FONT_SCALE_BASE: float = 1.0  # Base font scale for text fitting
PADDING: int = 20  # Pixels padding around text

# --- Gesture Mapping ---
SELECT_GESTURE = GestureType.CLOSED_FIST
SUMMON_GESTURE = GestureType.VICTORY
ZOOM_GESTURE = GestureType.POINTING  # Both hands must be this
PAN_GESTURE = GestureType.CLOSED_FIST


# --- Colors (BGR) ---
@dataclass
class MenuColors:
    NORMAL: Tuple[int, int, int] = (20, 20, 20)  # Very Dark Gray
    HOVER: Tuple[int, int, int] = (60, 60, 60)  # Dark Gray
    SELECTED: Tuple[int, int, int] = (0, 100, 0)  # Dark Green
    CONFIRM: Tuple[int, int, int] = (0, 255, 0)  # Bright Green
    BACKGROUND: Tuple[int, int, int] = (
        0,
        0,
        0,
    )  # Black (unused by renderer for item fill)
    TEXT: Tuple[int, int, int] = (200, 200, 200)  # Light Gray
    BORDER: Tuple[int, int, int] = (100, 100, 100)  # Gray
