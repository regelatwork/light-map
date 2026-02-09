from typing import Tuple
from dataclasses import dataclass
from light_map.common_types import MenuItem, MenuActions, GestureType

# --- Constants ---
LOCK_DELAY: float = 0.3  # Seconds to pin cursor history
GRACE_PERIOD: float = 0.2  # Seconds to wait before resetting prime if gesture is lost
PRIMING_TIME: float = 0.8  # Seconds to hold gesture to trigger action
SUMMON_TIME: float = 1.0  # Seconds to hold summon gesture to open menu
ZOOM_DELAY: float = 0.5  # Seconds to hold two-hand pointing to enter zoom mode

ITEM_WIDTH_PCT: float = 0.6  # Width of menu items relative to screen width
MAX_VISIBLE_ITEMS: int = 5  # Maximum number of items to show at once
FONT_SCALE_BASE: float = 1.0  # Base font scale for text fitting
PADDING: int = 20  # Pixels padding around text

# --- Gesture Mapping ---
SELECT_GESTURE = GestureType.CLOSED_FIST
SUMMON_GESTURE = GestureType.VICTORY
ZOOM_GESTURE = GestureType.POINTING  # Both hands must be this
PAN_GESTURE = GestureType.OPEN_PALM


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
            title="Map Controls",
            action_id=MenuActions.MAP_CONTROLS,
            should_close_on_trigger=True,
        ),
        MenuItem(
            title="Map Settings",
            children=[
                MenuItem(
                    title="Rotate CW",
                    action_id=MenuActions.ROTATE_CW,
                    should_close_on_trigger=False,
                ),
                MenuItem(
                    title="Rotate CCW",
                    action_id=MenuActions.ROTATE_CCW,
                    should_close_on_trigger=False,
                ),
                MenuItem(
                    title="Reset View",
                    action_id=MenuActions.RESET_VIEW,
                    should_close_on_trigger=False,
                ),
                MenuItem(
                    title="Calibrate Scale",
                    action_id=MenuActions.CALIBRATE_SCALE,
                    should_close_on_trigger=True,
                ),
            ],
        ),
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
