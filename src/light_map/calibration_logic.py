import cv2
import numpy as np
from typing import Optional

from .camera import Camera
from .projector import generate_calibration_pattern, compute_projector_homography


def run_calibration_sequence(
    camera: Camera, width: int = 1920, height: int = 1080, rows: int = 6, cols: int = 9
) -> Optional[np.ndarray]:
    """
    Runs the projector calibration sequence using an existing camera instance.

    Args:
        camera: An open Camera instance.
        width: Projector width.
        height: Projector height.
        rows: Chessboard rows.
        cols: Chessboard cols.

    Returns:
        The computed homography matrix, or None if failed.
    """

    # Setup Fullscreen Window
    window_name = "calibration_pattern"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    try:
        # Generate Pattern
        pattern_img, params = generate_calibration_pattern(width, height, rows, cols)

        cv2.imshow(window_name, pattern_img)
        print("Displaying pattern. Waiting 2 seconds for projector/camera to settle...")

        # Pump the event loop to ensure window draws
        for _ in range(20):
            cv2.waitKey(100)

        # Capture Image
        print("Capturing image...")
        # Read a few frames to let auto-exposure settle if needed,
        # though waiting 2s above usually handles it.
        # But we are in a tight loop potentially, so flush the buffer.
        for _ in range(5):
            camera.read()

        frame = camera.read()

        if frame is None:
            print("Failed to capture image.")
            return None

        # Save debug image
        cv2.imwrite("captured_frame.jpg", frame)
        print("Saved capture to captured_frame.jpg")

        # Compute Homography
        matrix = compute_projector_homography(frame, params)
        return matrix

    except Exception as e:
        print(f"Error computing homography: {e}")
        return None
    finally:
        # Ensure window is closed
        cv2.destroyWindow(window_name)
