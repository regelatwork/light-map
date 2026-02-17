import cv2
import numpy as np
from typing import Optional, Tuple

from .camera import Camera
from .projector import generate_calibration_pattern, compute_projector_homography


def run_calibration_sequence(
    camera: Camera, width: int = 1920, height: int = 1080, rows: int = 6, cols: int = 9
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Runs the projector calibration sequence using an existing camera instance.
    Returns (matrix, cam_pts, proj_pts) or None.
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

        return compute_projector_homography(frame, params)

    except Exception as e:
        print(f"Error computing homography: {e}")
        return None
    finally:
        cv2.destroyWindow(window_name)


def calculate_ppi_from_frame(
    frame: np.ndarray, projector_matrix: np.ndarray, target_dist_mm: float = 100.0
) -> Optional[float]:
    """
    Detects two ArUco markers (ID 0 and ID 1) in the frame and calculates Projector PPI.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # ArUco Config
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is None or len(ids) < 2:
        return None

    ids = ids.flatten()

    # Check for ID 0 and ID 1
    if 0 not in ids or 1 not in ids:
        return None

    idx0 = np.where(ids == 0)[0][0]
    idx1 = np.where(ids == 1)[0][0]

    # Get centers
    # corners[i] is (1, 4, 2)
    c0 = np.mean(corners[idx0][0], axis=0)
    c1 = np.mean(corners[idx1][0], axis=0)

    p1_cam = np.array(c0, dtype=np.float32)
    p2_cam = np.array(c1, dtype=np.float32)

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
