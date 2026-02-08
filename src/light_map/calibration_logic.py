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

        for _ in range(20):
            cv2.waitKey(100)

        print("Capturing image...")
        for _ in range(5):
            camera.read()

        frame = camera.read()

        if frame is None:
            print("Failed to capture image.")
            return None

        cv2.imwrite("captured_frame.jpg", frame)
        print("Saved capture to captured_frame.jpg")

        matrix = compute_projector_homography(frame, params)
        return matrix

    except Exception as e:
        print(f"Error computing homography: {e}")
        return None
    finally:
        cv2.destroyWindow(window_name)


def calculate_ppi_from_frame(
    frame: np.ndarray, projector_matrix: np.ndarray, target_dist_mm: float = 100.0
) -> Optional[float]:
    """
    Detects two black square markers in the frame and calculates Projector PPI.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold to handle uneven lighting
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter candidates
    candidates = []
    min_area = 100  # px
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        # Check squareness
        rect = cv2.minAreaRect(cnt)
        w, h = rect[1]
        if w == 0 or h == 0:
            continue
        aspect_ratio = min(w, h) / max(w, h)

        if aspect_ratio > 0.7:  # Roughly square
            # Calculate centroid
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                candidates.append((area, (cx, cy)))

    # Sort by area (largest first) and pick top 2
    candidates.sort(key=lambda x: x[0], reverse=True)

    if len(candidates) < 2:
        return None

    p1_cam = np.array(candidates[0][1], dtype=np.float32)
    p2_cam = np.array(candidates[1][1], dtype=np.float32)

    # Transform to Projector Space
    # Reshape for perspectiveTransform: (N, 1, 2)
    pts_cam = np.array([p1_cam, p2_cam]).reshape(-1, 1, 2)
    pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix)

    p1_proj = pts_proj[0][0]
    p2_proj = pts_proj[1][0]

    dist_px = np.linalg.norm(p1_proj - p2_proj)

    # PPI = Pixels / Inches
    dist_inches = target_dist_mm / 25.4
    ppi = dist_px / dist_inches

    return ppi
