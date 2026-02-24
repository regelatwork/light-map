import cv2
import numpy as np
import logging
from typing import Optional, Tuple, Dict

from .camera import Camera
from .projector import generate_calibration_pattern, compute_projector_homography


def run_calibration_sequence(
    camera: Camera,
    projector_width: int = 1920,
    projector_height: int = 1080,
    rows: int = 13,
    cols: int = 18,
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
        pattern_img, params = generate_calibration_pattern(
            projector_width, projector_height, rows, cols, border_size=30
        )

        cv2.imshow(window_name, pattern_img)
        logging.info(
            "Displaying pattern. Waiting 2 seconds for projector/camera to settle..."
        )

        for _ in range(20):
            cv2.waitKey(100)

        logging.info("Capturing image...")
        for _ in range(5):
            camera.read()

        frame = camera.read()

        if frame is None:
            logging.error("Failed to capture image.")
            return None

        cv2.imwrite("captured_frame.jpg", frame)
        logging.info("Saved capture to captured_frame.jpg")

        return compute_projector_homography(frame, params)

    except Exception as e:
        logging.error("Error computing homography: %s", e)
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


def calibrate_extrinsics(
    frame: np.ndarray,
    projector_matrix: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    token_heights: Dict[int, float],
    ppi: float,
    ground_points_cam: Optional[np.ndarray] = None,
    ground_points_proj: Optional[np.ndarray] = None,
    known_targets: Optional[Dict[int, Tuple[float, float]]] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Estimates Camera Extrinsics (R, t) using ArUco markers with known heights.

    Args:
        frame: The camera frame containing ArUco markers.
        projector_matrix: Homography (Camera -> Projector).
        camera_matrix: Camera intrinsic matrix.
        dist_coeffs: Camera distortion coefficients.
        token_heights: Mapping of ArUco ID to token height in mm.
        ppi: Projector PPI (Pixels Per Inch).
        ground_points_cam: (N, 2) array of camera coordinates at Z=0.
        ground_points_proj: (N, 2) array of projector coordinates corresponding to ground_points_cam.
        known_targets: Optional mapping of ArUco ID to (x, y) projector coordinates.

    Returns:
        (rvec, tvec, obj_points, img_points) or None.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    corners, ids, rejected = detector.detectMarkers(gray)

    obj_points_list = []  # 3D points in World Space (mm)
    img_points_list = []  # 2D points in Camera Space (px)

    ppi_mm = ppi / 25.4

    # 1. Add Ground Points (Z=0) from Step 1 if available
    if ground_points_cam is not None and ground_points_proj is not None:
        for i in range(len(ground_points_cam)):
            px, py = ground_points_proj[i]
            wx = px / ppi_mm
            wy = py / ppi_mm
            wz = 0.0
            obj_points_list.append([wx, wy, wz])
            img_points_list.append(ground_points_cam[i])

    # 2. Add Token Points (Z=h)
    if ids is not None:
        ids = ids.flatten()
        for i, aruco_id in enumerate(ids):
            if aruco_id not in token_heights:
                continue

            h = token_heights[aruco_id]
            c_cam = np.mean(corners[i][0], axis=0)

            # Find (X, Y)
            if known_targets and aruco_id in known_targets:
                px, py = known_targets[aruco_id]
            else:
                # Fallback to homography projection (estimate from top of token)
                pts_cam = np.array([c_cam], dtype=np.float32).reshape(-1, 1, 2)
                pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix).reshape(
                    -1, 2
                )
                px, py = pts_proj[0]

            wx = px / ppi_mm
            wy = py / ppi_mm
            wz = h

            obj_points_list.append([wx, wy, wz])
            img_points_list.append(c_cam)

    if len(obj_points_list) < 4:
        logging.warning(
            "Extrinsics: Not enough points detected (need at least 4 combined points)."
        )
        return None

    obj_points = np.array(obj_points_list, dtype=np.float32)
    img_points = np.array(img_points_list, dtype=np.float32)

    # Solve PnP
    # Use an initial guess for a camera looking DOWN at the table from above.
    # A 180-degree rotation around X (rvec = [pi, 0, 0]) is a good starting point.
    rvec_guess = np.array([np.pi, 0, 0], dtype=np.float32).reshape(3, 1)
    tvec_guess = np.array([0, 0, 1000], dtype=np.float32).reshape(3, 1)

    ret, rvec, tvec = cv2.solvePnP(
        obj_points,
        img_points,
        camera_matrix,
        dist_coeffs,
        rvec=rvec_guess,
        tvec=tvec_guess,
        useExtrinsicGuess=True,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if ret:
        # Physical plausibility check: tz MUST be positive for the table to be in front of the camera
        if tvec[2] < 0:
            logging.warning("Extrinsics: solvePnP returned inverted solution (tz < 0). Attempting flip.")
            # Flip the solution
            R, _ = cv2.Rodrigues(rvec)
            C = -R.T @ tvec
            
            R_flip = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)
            R_new = R_flip @ R
            rvec_new, _ = cv2.Rodrigues(R_new)
            tvec_new = -R_new @ C
            
            rvec, tvec = rvec_new, tvec_new

        return rvec, tvec, obj_points, img_points

    return None
