import cv2
import tkinter as tk
import logging
import sys
import os
import numpy as np
from logging.handlers import RotatingFileHandler
from typing import Tuple, Optional
from light_map.core.storage import StorageManager
from light_map.core.constants import (
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    WINDOW_CLOSE_CHECK_DELAY_FRAMES,
    FALLBACK_SCREEN_RESOLUTION,
    DASHED_CIRCLE_DASH_DEG,
)

_DEFAULT_STORAGE = StorageManager()


class ProjectorWindow:
    def __init__(self, name: str, width: int, height: int):
        self.name = name
        self.width = width
        self.height = height
        self.closed = False
        self._frames_shown = 0

        # Create window and set to fullscreen
        cv2.namedWindow(self.name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(self.name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        # Briefly pump the loop to help initialization
        cv2.waitKey(1)

    def get_key(self) -> int:
        # In the current architecture, keys are handled by MainLoopController via waitKey(1)
        return -1

    def update_image(self, bgr_frame: np.ndarray) -> int:
        if self.closed:
            return -1

        try:
            cv2.imshow(self.name, bgr_frame)
            self._frames_shown += 1
            return cv2.waitKey(1)
        except Exception as e:
            logging.error(f"Error updating window {self.name}: {e}")
            self.closed = True
            return -1

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                cv2.destroyWindow(self.name)
            except Exception:
                pass

    def is_closed(self) -> bool:
        if self.closed:
            return True

        # Headless/Mock mode check
        if os.environ.get("MOCK_CAMERA") == "1":
            return False

        # Only check window properties after a few frames have been shown
        if self._frames_shown < WINDOW_CLOSE_CHECK_DELAY_FRAMES:
            return False

        try:
            # getWindowProperty returns 0 if the window is invisible or closed.
            # It sometimes returns -1 if the property is not yet available or during transients.
            prop = cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE)
            if prop == 0:
                logging.info(
                    f"Window closure detected via getWindowProperty (prop={prop})"
                )
                self.closed = True
        except Exception as e:
            # Only treat exceptions as closure if they persist or indicate invalid window handle
            logging.info(f"Ignored exception in getWindowProperty: {e}")
            pass

        return self.closed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def draw_text_with_background(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font=cv2.FONT_HERSHEY_SIMPLEX,
    scale=0.5,
    color=(255, 255, 255),
    thickness=1,
    bg_color=(0, 0, 0),
    alpha=0.75,
    padding=5,
):
    """Draws text with a semi-transparent rectangular background."""
    text = str(text)
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = pos

    # Background rectangle
    bg_rect_x1 = x - padding
    bg_rect_y1 = y - text_height - padding
    bg_rect_x2 = x + text_width + padding
    bg_rect_y2 = y + baseline + padding

    # Clip to image boundaries
    h, w = img.shape[:2]
    bg_rect_x1 = max(0, bg_rect_x1)
    bg_rect_y1 = max(0, bg_rect_y1)
    bg_rect_x2 = min(w, bg_rect_x2)
    bg_rect_y2 = min(h, bg_rect_y2)

    if bg_rect_x2 <= bg_rect_x1 or bg_rect_y2 <= bg_rect_y1:
        # Rectangle is outside or has zero area
        cv2.putText(img, text, (x, y), font, scale, color, thickness)
        return

    # Draw background
    channels = img.shape[2]
    if channels == 4:
        # For 4-channel (BGRA), we set the background color and alpha directly
        # to ensure it's preserved in the patch.
        bg_bgr = bg_color[:3]
        bg_alpha = int(alpha * 255)
        
        # We blend the background box with whatever is already in the buffer
        # using a manual blend to ensure the alpha is handled correctly.
        roi = img[bg_rect_y1:bg_rect_y2, bg_rect_x1:bg_rect_x2]
        
        # Source (the box we are drawing)
        src_alpha = bg_alpha
        
        # Simple blend: src * alpha + dst * (1-alpha)
        # Note: Since this is usually a fresh buffer, dst is 0.
        roi[:, :, :3] = (roi[:, :, :3].astype(np.uint16) * (255 - src_alpha) // 255 + 
                         np.array(bg_bgr, dtype=np.uint16) * src_alpha // 255).astype(np.uint8)
        
        # For alpha, we take the maximum of current and new alpha (non-additive for UI boxes)
        roi[:, :, 3] = np.maximum(roi[:, :, 3], src_alpha)
    else:
        # For 3-channel (BGR), use standard addWeighted
        sub_img = img[bg_rect_y1:bg_rect_y2, bg_rect_x1:bg_rect_x2]
        rect = np.full(sub_img.shape, bg_color[:3], dtype=np.uint8)
        res = cv2.addWeighted(sub_img, 1 - alpha, rect, alpha, 0)
        img[bg_rect_y1:bg_rect_y2, bg_rect_x1:bg_rect_x2] = res

    # Draw text
    full_text_color = color if len(color) == channels else (tuple(color) + (255,) if channels == 4 else color[:3])
    cv2.putText(img, text, (x, y), font, scale, full_text_color, thickness)


def setup_logging(level=logging.INFO, log_file: Optional[str] = None):
    """
    Configures the root logger with console and file handlers.

    Args:
        level: Logging level (e.g., logging.INFO).
        log_file: Path to the log file. Defaults to XDG-compliant state path if None.
    """
    if log_file is None:
        log_file = _DEFAULT_STORAGE.get_state_path("light_map.log")

    # Clear existing handlers to avoid duplicates if called multiple times
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    root_logger.setLevel(level)

    # Console Handler (Stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (with rotation)
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to initialize file logging: {e}")

    logging.info("Logging initialized at level %s", logging.getLevelName(level))


def get_screen_resolution() -> Tuple[int, int]:
    """
    Detects the current screen resolution using tkinter.
    Returns (width, height).
    """
    try:
        root = tk.Tk()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception as e:
        logging.warning(
            "Failed to detect screen resolution: %s. Falling back to %dx%d.",
            e,
            FALLBACK_SCREEN_RESOLUTION[0],
            FALLBACK_SCREEN_RESOLUTION[1],
        )
        return FALLBACK_SCREEN_RESOLUTION


def draw_dashed_circle(
    img, center, radius, color, thickness=1, dash_length_deg=DASHED_CIRCLE_DASH_DEG
):
    """Draws a dashed circle using multiple ellipse arcs."""
    for i in range(0, 360, dash_length_deg * 2):
        cv2.ellipse(
            img,
            center,
            (radius, radius),
            0,
            i,
            i + dash_length_deg,
            color,
            thickness,
        )


def parse_color(
    color_str: Optional[str], default=(255, 255, 0)
) -> Tuple[int, int, int]:
    """
    Parses a color string (e.g. '#RRGGBB' or 'red') into a BGR tuple.
    Returns default if parsing fails or input is None.
    """
    if not color_str:
        return default

    # Handle hex colors
    if color_str.startswith("#"):
        hex_val = color_str.lstrip("#")
        try:
            if len(hex_val) == 6:
                r, g, b = (
                    int(hex_val[0:2], 16),
                    int(hex_val[2:4], 16),
                    int(hex_val[4:6], 16),
                )
                return (b, g, r)  # BGR
            elif len(hex_val) == 3:
                r, g, b = (
                    int(hex_val[0] * 2, 16),
                    int(hex_val[1] * 2, 16),
                    int(hex_val[2] * 2, 16),
                )
                return (b, g, r)  # BGR
        except ValueError:
            pass

    # Basic CSS color names mapping to BGR
    css_colors = {
        "red": (0, 0, 255),
        "green": (0, 255, 0),
        "blue": (255, 0, 0),
        "yellow": (0, 255, 255),
        "cyan": (255, 255, 0),
        "magenta": (255, 0, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "orange": (0, 165, 255),
        "purple": (128, 0, 128),
        "pink": (203, 192, 255),
    }

    return css_colors.get(color_str.lower(), default)
