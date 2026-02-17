import tkinter as tk
from typing import Tuple


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
        print(
            f"Warning: Failed to detect screen resolution: {e}. Falling back to 1920x1080."
        )
        return 1920, 1080
