import cv2
import tkinter as tk
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Tuple


def setup_logging(level=logging.INFO, log_file="light_map.log"):
    """
    Configures the root logger with console and file handlers.
    
    Args:
        level: Logging level (e.g., logging.INFO).
        log_file: Path to the log file.
    """
    # Clear existing handlers to avoid duplicates if called multiple times
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    root_logger.setLevel(level)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (with rotation)
    try:
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
