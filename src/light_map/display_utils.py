import cv2
import tkinter as tk
import logging
import sys
import os
import numpy as np
from logging.handlers import RotatingFileHandler
from typing import Tuple, Optional
from light_map.core.storage import StorageManager

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

    def update_image(self, bgr_frame: np.ndarray):
        if self.closed:
            return

        cv2.imshow(self.name, bgr_frame)
        self._frames_shown += 1
        # Note: We rely on MainLoopController.tick() calling cv2.waitKey(1)
        # to pump the event loop and update the window.

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

        # Only check window properties after a few frames have been shown
        if self._frames_shown < 100:
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


def draw_text_with_background(
    img: np.ndarray,
    text: str,
    pos: Tuple[int, int],
    font=cv2.FONT_HERSHEY_SIMPLEX,
    scale=0.5,
    color=(255, 255, 255),
    thickness=1,
    bg_color=(0, 0, 0),
    alpha=0.6,
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

    # Draw background with alpha blending
    sub_img = img[bg_rect_y1:bg_rect_y2, bg_rect_x1:bg_rect_x2]
    rect = np.full(sub_img.shape, bg_color, dtype=np.uint8)
    res = cv2.addWeighted(sub_img, 1 - alpha, rect, alpha, 0)
    img[bg_rect_y1:bg_rect_y2, bg_rect_x1:bg_rect_x2] = res

    # Draw text
    cv2.putText(img, text, (x, y), font, scale, color, thickness)


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
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
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
            "Failed to detect screen resolution: %s. Falling back to 1920x1080.", e
        )
        return 1920, 1080


def draw_dashed_circle(img, center, radius, color, thickness=1, dash_length_deg=12):
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
