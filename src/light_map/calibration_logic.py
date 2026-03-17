import cv2
import numpy as np
import logging
import time
from typing import Optional, Tuple, Dict, List

from .camera import Camera
from .projector import generate_calibration_pattern, compute_projector_homography
from .display_utils import ProjectorWindow


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
    # Setup Projector Window (using tkinter to hide cursor)
    win = ProjectorWindow("calibration_pattern", projector_width, projector_height)

    try:
        # Generate Pattern
        pattern_img, params = generate_calibration_pattern(
            projector_width, projector_height, rows, cols, border_size=30
        )

        win.update_image(pattern_img)
        logging.info(
            "Displaying pattern. Waiting 2 seconds for projector/camera to settle..."
        )

        for _ in range(20):
            win.update_image(pattern_img)
            time.sleep(0.1)

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
        win.close()


def calculate_ppi_from_frame(
    frame: np.ndarray,
    projector_matrix: np.ndarray,
    target_dist_mm: float = 100.0,
    aruco_corners: Optional[Tuple[np.ndarray, ...]] = None,
    aruco_ids: Optional[np.ndarray] = None,
) -> Optional[float]:
    """
    Calculates Projector PPI using pre-detected ArUco markers or internal detection from frame.
    """
    if aruco_ids is None or aruco_corners is None:
        if frame is None:
            return None
        # Internal fallback detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        aruco_corners, aruco_ids, _ = detector.detectMarkers(gray)

    if aruco_ids is None or len(aruco_ids) < 2 or aruco_corners is None:
        return None

    ids = aruco_ids.flatten()

    # Check for ID 0 and ID 1
    if 0 not in ids or 1 not in ids:
        return None

    idx0 = np.where(ids == 0)[0][0]
    idx1 = np.where(ids == 1)[0][0]

    # Get centers
    # corners[i] is (1, 4, 2)
    c0 = np.mean(aruco_corners[idx0][0], axis=0)
    c1 = np.mean(aruco_corners[idx1][0], axis=0)

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
    distortion_coefficients: np.ndarray,
    token_heights: Dict[int, float],
    ppi: float,
    ground_points_camera: Optional[np.ndarray] = None,
    ground_points_projector: Optional[np.ndarray] = None,
    known_targets: Optional[Dict[int, Tuple[float, float]]] = None,
    aruco_corners: Optional[Tuple[np.ndarray, ...]] = None,
    aruco_ids: Optional[np.ndarray] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    Estimates Camera Extrinsics (R, t) using pre-detected ArUco markers or internal detection.

    Args:
        frame: The camera frame containing ArUco markers (fallback if corners/ids missing).
        projector_matrix: Homography (Camera -> Projector).
        camera_matrix: Camera intrinsic matrix.
        distortion_coefficients: Camera distortion coefficients.
        token_heights: Mapping of ArUco ID to token height in mm.
        ppi: Projector PPI (Pixels Per Inch).
        ground_points_camera: (N, 2) array of camera coordinates at Z=0.
        ground_points_projector: (N, 2) array of projector coordinates corresponding to ground_points_camera.
        known_targets: Optional mapping of ArUco ID to (x, y) projector coordinates.
        aruco_corners: Pre-detected ArUco corners.
        aruco_ids: Pre-detected ArUco IDs.

    Returns:
        (rotation_vector, translation_vector, object_points, image_points) or None.
    """
    if aruco_ids is None or aruco_corners is None:
        if frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            parameters = cv2.aruco.DetectorParameters()
            detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
            aruco_corners, aruco_ids, _ = detector.detectMarkers(gray)

    object_points_list = []  # 3D points in World Space (mm)
    image_points_list = []  # 2D points in Camera Space (px)

    ppi_mm = ppi / 25.4

    # 1. Add Ground Points (Z=0) from Step 1 if available
    if ground_points_camera is not None and ground_points_projector is not None:
        for i in range(len(ground_points_camera)):
            px, py = ground_points_projector[i]
            wx = px / ppi_mm
            wy = py / ppi_mm
            wz = 0.0
            object_points_list.append([wx, wy, wz])
            image_points_list.append(ground_points_camera[i])

    # 2. Add Token Points (Z=h)
    if aruco_ids is not None and aruco_corners is not None:
        ids = aruco_ids.flatten()
        for i, aruco_id in enumerate(ids):
            if aruco_id not in token_heights:
                continue

            h = token_heights[aruco_id]
            c_cam = np.mean(aruco_corners[i][0], axis=0)

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

            object_points_list.append([wx, wy, wz])
            image_points_list.append(c_cam)

    if len(object_points_list) < 4:
        logging.warning(
            "Extrinsics: Not enough points detected (need at least 4 combined points)."
        )
        return None

    object_points = np.array(object_points_list, dtype=np.float32)
    image_points = np.array(image_points_list, dtype=np.float32)

    num_tokens = len(aruco_ids) if aruco_ids is not None else 0
    num_ground = len(object_points_list) - num_tokens

    logging.info(
        f"Extrinsics: Solving for {len(object_points)} points ({num_ground} ground, {num_tokens} tokens)."
    )

    # Solve PnP
    # SQPNP is highly robust to both planar and non-planar configurations.
    # We still provide an initial guess to help it converge to the "looking down" solution.
    rotation_vector_guess = np.array([np.pi, 0, 0], dtype=np.float32).reshape(3, 1)
    translation_vector_guess = np.array([0, 0, 1000], dtype=np.float32).reshape(3, 1)

    ret, rotation_vector, translation_vector = cv2.solvePnP(
        object_points,
        image_points,
        camera_matrix,
        distortion_coefficients,
        rvec=rotation_vector_guess,
        tvec=translation_vector_guess,
        useExtrinsicGuess=True,
        flags=cv2.SOLVEPNP_SQPNP,
    )

    if ret:
        # Physical plausibility check: tz MUST be positive for the table to be in front of the camera
        if translation_vector[2] < 0:
            logging.warning(
                "Extrinsics: solvePnP returned inverted solution (tz < 0). Attempting flip."
            )
            # Flip the solution
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            camera_center = -(rotation_matrix.T @ translation_vector)

            rotation_matrix_flip = np.array(
                [[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32
            )
            rotation_matrix_new = rotation_matrix_flip @ rotation_matrix
            rotation_vector_new, _ = cv2.Rodrigues(rotation_matrix_new)
            translation_vector_new = -rotation_matrix_new @ camera_center

            rotation_vector, translation_vector = (
                rotation_vector_new,
                translation_vector_new,
            )

        return rotation_vector, translation_vector, object_points, image_points

    return None


def calibrate_projector_3d(
    correspondences: List[Tuple[np.ndarray, np.ndarray]],
    projector_resolution: Tuple[int, int],
    initial_intrinsic_matrix: Optional[np.ndarray] = None,
    initial_distortion_coefficients: Optional[np.ndarray] = None,
) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]]:
    """
    Computes Projector Intrinsics and Extrinsics using 3D-to-2D correspondences.

    Args:
        correspondences: List of (world_point_3d, projector_point_2d) tuples.
                         world_point_3d is (3,) array [X, Y, Z] in mm.
                         projector_point_2d is (2,) array [u, v] in pixels.
        projector_resolution: (width, height) of the projector.
        initial_intrinsic_matrix: Optional initial intrinsic matrix.
        initial_distortion_coefficients: Optional initial distortion coefficients.

    Returns:
        (intrinsic_matrix, distortion_coefficients, rotation_vector, translation_vector, rms) or None if calibration fails.
    """
    if len(correspondences) < 10:
        logging.warning(
            "calibrate_projector_3d: Not enough points (need at least 10 for stability, got %d).",
            len(correspondences),
        )
        return None

    # OpenCV calibrateCamera expects a list of views.
    # Each view should be a (N, 3) or (N, 2) float32 array.
    # We use ascontiguousarray to ensure the memory layout matches C++ expectations.
    # We explicitly reshape to (-1, 1, 3) and (-1, 1, 2) as this is the most robust format
    # that handles both list-of-lists and flattening issues in cv2.
    object_points = [
        np.ascontiguousarray([c[0] for c in correspondences], dtype=np.float32).reshape(
            -1, 1, 3
        )
    ]
    image_points = [
        np.ascontiguousarray([c[1] for c in correspondences], dtype=np.float32).reshape(
            -1, 1, 2
        )
    ]

    # Final count validation before OpenCV call
    for i in range(len(object_points)):
        if object_points[i].shape[0] != image_points[i].shape[0]:
            raise ValueError(
                f"Point count mismatch in View {i}: object_points has {object_points[i].shape[0]}, "
                f"image_points has {image_points[i].shape[0]}. Check for NumPy broadcasting errors."
            )

    if initial_intrinsic_matrix is None:
        # Provide a reasonable initial guess for the intrinsic matrix
        # f = max(width, height), principal point = center
        width, height = projector_resolution
        focal_length = max(width, height)
        initial_intrinsic_matrix = np.array(
            [[focal_length, 0, width / 2], [0, focal_length, height / 2], [0, 0, 1]],
            dtype=np.float32,
        )
    else:
        initial_intrinsic_matrix = np.ascontiguousarray(
            initial_intrinsic_matrix, dtype=np.float32
        )

    if initial_distortion_coefficients is None:
        initial_distortion_coefficients = np.zeros(5, dtype=np.float32)
    else:
        initial_distortion_coefficients = np.ascontiguousarray(
            initial_distortion_coefficients, dtype=np.float32
        )

    flags = cv2.CALIB_USE_INTRINSIC_GUESS

    # For projectors, we often assume no skew and potentially fx=fy
    # flags |= cv2.CALIB_FIX_ASPECT_RATIO

    try:
        # Using positional arguments for the matrices can be more robust in some cv2 versions
        (
            ret,
            intrinsic_matrix,
            distortion_coefficients,
            rotation_vectors,
            translation_vectors,
        ) = cv2.calibrateCamera(
            object_points,
            image_points,
            projector_resolution,
            initial_intrinsic_matrix,
            initial_distortion_coefficients,
            flags=flags,
        )

        if ret:
            # calibrateCamera returns a list of rvecs/tvecs (one per 'view').
            # Since we treat all points as one 'view', we take the first one.
            return (
                intrinsic_matrix,
                distortion_coefficients,
                rotation_vectors[0],
                translation_vectors[0],
                ret,
            )

    except Exception as e:
        logging.error("calibrate_projector_3d: Error during calibration: %s", e)

    return None
