from typing import Tuple
from dataclasses import dataclass
from src.light_map.common_types import MenuItem, MenuActions, GestureType

# --- Constants ---
LOCK_DELAY: float = 0.3  # Seconds to pin cursor history
GRACE_PERIOD: float = 0.2  # Seconds to wait before resetting prime if gesture is lost
PRIMING_TIME: float = 0.8  # Seconds to hold gesture to trigger action
SUMMON_TIME: float = 1.0  # Seconds to hold summon gesture to open menu
ITEM_WIDTH_PCT: float = 0.6  # Width of menu items relative to screen width
MAX_VISIBLE_ITEMS: int = 5  # Maximum number of items to show at once
FONT_SCALE_BASE: float = 1.0  # Base font scale for text fitting
PADDING: int = 20  # Pixels padding around text

# --- Gesture Mapping ---
SELECT_GESTURE = GestureType.CLOSED_FIST
SUMMON_GESTURE = GestureType.VICTORY


# --- Colors (BGR) ---
@dataclass
class MenuColors:
    NORMAL: Tuple[int, int, int] = (255, 255, 255)  # White
    HOVER: Tuple[int, int, int] = (0, 255, 255)  # Yellow
    SELECTED: Tuple[int, int, int] = (0, 255, 0)  # Green
    BACKGROUND: Tuple[int, int, int] = (50, 50, 50)  # Dark Gray
    TEXT: Tuple[int, int, int] = (0, 0, 0)  # Black (for text on background)
    BORDER: Tuple[int, int, int] = (200, 200, 200)  # Light Gray


# --- Menu Structure ---
ROOT_MENU = MenuItem(
    title="Main Menu",
    children=[
        MenuItem(
            title="Calibrate",
            action_id=MenuActions.CALIBRATE,
            should_close_on_trigger=True,
        ),
        MenuItem(
            title="Options",
            children=[
                MenuItem(
                    title="Toggle Debug",
                    action_id=MenuActions.TOGGLE_DEBUG,
                    should_close_on_trigger=False,
                ),
            ],
        ),
        MenuItem(
            title="Exit", action_id=MenuActions.EXIT, should_close_on_trigger=True
        ),
    ],
)
