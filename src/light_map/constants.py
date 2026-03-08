"""
Global constants for the Light Map project.
Contains magic numbers and shared configuration defaults.
"""


# --- Visual / Rendering Constants ---
VISIBILITY_SHROUD_ALPHA = 150  # Default dimming for non-visible explored areas
ALPHA_OPAQUE = 255
ALPHA_TRANSPARENT = 0

# --- Cursor / UI Constants ---
CURSOR_RADIUS = 12
CURSOR_COLOR_BGRA = (0, 255, 255, 255)  # Yellow
CURSOR_THICKNESS = 2
CURSOR_CROSSHAIR_SIZE = 5

# --- Mask / Grid Constants ---
# Resolution of the FoW mask relative to grid units (16px = 1 grid unit)
GRID_MASK_PPI = 16.0

# --- Gesture Recognition Landmarks (MediaPipe) ---
WRIST = 0
THUMB_TIP = 4
THUMB_IP = 3
INDEX_TIP = 8
INDEX_PIP = 6
INDEX_MCP = 5
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18
PINKY_MCP = 17

# --- Calibration Defaults ---
DEFAULT_CHECKERBOARD_DIMS = (6, 9)

# --- AppConfig Defaults ---
DEFAULT_PROJECTOR_RESOLUTION = (4608, 2592)
DEFAULT_HAND_MASK_PADDING = 30
DEFAULT_PROJECTOR_PPI = 96.0
DEFAULT_POINTER_EXTENSION_INCHES = 2.0
DEFAULT_INSPECTION_LINGER_DURATION = 10.0
DEFAULT_DOOR_THICKNESS_MULTIPLIER = 3.0

# --- Logging Constants ---
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

# --- Window / Display Constants ---
WINDOW_CLOSE_CHECK_DELAY_FRAMES = 100
FALLBACK_SCREEN_RESOLUTION = (1920, 1080)

# --- Drawing Constants ---
DASHED_CIRCLE_DASH_DEG = 12
