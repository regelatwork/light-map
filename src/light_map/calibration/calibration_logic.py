import logging
import time

import cv2
import numpy as np

from light_map.core.display_utils import ProjectorWindow
from light_map.rendering.projector import (
    compute_projector_homography,
    generate_calibration_pattern,
)
from light_map.vision.infrastructure.camera import Camera


def run_calibration_sequence(
    camera: Camera,
    projector_width: int = 1920,
    projector_height: int = 1080,
    rows: int = 13,
    cols: int = 18,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
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
        logging.info("Displaying pattern. Waiting 2 seconds for projector/camera to settle...")

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

        # Detect ArUco markers for orientation correction
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        aruco_corners, aruco_ids, _ = detector.detectMarkers(gray)

        if aruco_ids is not None:
            logging.info(f"Detected ArUco markers: {aruco_ids.flatten()}. Using for orientation.")

        return compute_projector_homography(
            frame, params, aruco_corners=aruco_corners, aruco_ids=aruco_ids
        )

    except Exception as e:
        logging.error("Error computing homography: %s", e)
        return None
    finally:
        win.close()


def calculate_ppi_from_frame(
    frame: np.ndarray,
    projector_matrix: np.ndarray,
    target_dist_mm: float = 100.0,
    aruco_corners: tuple[np.ndarray, ...] | None = None,
    aruco_ids: np.ndarray | None = None,
) -> float | None:
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

    # Check for ID 40 and ID 41
    if 40 not in ids or 41 not in ids:
        return None

    idx0 = np.where(ids == 40)[0][0]
    idx1 = np.where(ids == 41)[0][0]

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
    token_heights: dict[int, float],
    ppi: float,
    ground_points_camera: np.ndarray | None = None,
    ground_points_projector: np.ndarray | None = None,
    known_targets: dict[int, tuple[float, float]] | None = None,
    aruco_corners: tuple[np.ndarray, ...] | None = None,
    aruco_ids: np.ndarray | None = None,
    token_sizes: dict[int, int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """
    Estimates Camera Extrinsics (R, t) using pre-detected ArUco markers or internal detection.

    Args:
        ...
        token_sizes: Mapping of ArUco ID to token size (inches or whatever unit ppi is in).
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

    # 2. Add Token Points (Z=h) - Using all 4 corners per token
    if aruco_ids is not None and aruco_corners is not None:
        ids = aruco_ids.flatten()
        for i, aruco_id in enumerate(ids):
            if aruco_id not in token_heights:
                continue

            h = token_heights[aruco_id]
            # Use all 4 corners
            corners_cam = aruco_corners[i][0]  # (4, 2)

            # Find (X, Y) for each corner
            if known_targets and aruco_id in known_targets:
                # Use known center and size to derive projector corners
                px_c, py_c = known_targets[aruco_id]
                # Default size to 1.0 inch if missing
                size_inches = token_sizes.get(aruco_id, 1.0) if token_sizes else 1.0
                size_px = size_inches * ppi

                # ArUco corners are defined as TL, TR, BR, BL
                offsets = [
                    [-size_px / 2, -size_px / 2],
                    [size_px / 2, -size_px / 2],
                    [size_px / 2, size_px / 2],
                    [-size_px / 2, size_px / 2],
                ]
                for j in range(4):
                    px = px_c + offsets[j][0]
                    py = py_c + offsets[j][1]
                    object_points_list.append([px / ppi_mm, py / ppi_mm, h])
                    image_points_list.append(corners_cam[j])
            else:
                # Fallback to homography projection for each corner
                pts_cam = corners_cam.reshape(-1, 1, 2).astype(np.float32)
                pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix).reshape(-1, 2)

                for j in range(4):
                    px, py = pts_proj[j]
                    object_points_list.append([px / ppi_mm, py / ppi_mm, h])
                    image_points_list.append(corners_cam[j])

    if len(object_points_list) < 4:
        logging.warning(
            f"Extrinsics: Not enough points detected (need at least 4 combined points, got {len(object_points_list)})."
        )
        return None

    object_points = np.array(object_points_list, dtype=np.float32)
    image_points = np.array(image_points_list, dtype=np.float32)

    num_tokens = len(aruco_ids) if aruco_ids is not None else 0
    num_ground = len(object_points_list) - num_tokens

    logging.info(
        f"Extrinsics: Solving for {len(object_points)} points ({num_ground} ground, {num_tokens} tokens)."
    )

    # Pick Solver based on planarity
    # SQPNP is highly robust to both planar and non-planar configurations.
    is_planar = np.all(object_points[:, 2] == object_points[0, 2])

    if is_planar and len(object_points) >= 4:
        # IPPE returns 2 solutions for planar points
        ret, rvecs, tvecs, errs = cv2.solvePnPGeneric(
            object_points,
            image_points,
            camera_matrix,
            distortion_coefficients,
            flags=cv2.SOLVEPNP_IPPE,
        )
    else:
        # SQPNP only returns 1 solution
        # Note: We don't use useExtrinsicGuess here because we want to see the
        # raw solutions from the solver before filtering.
        ret, rvecs, tvecs, errs = cv2.solvePnPGeneric(
            object_points,
            image_points,
            camera_matrix,
            distortion_coefficients,
            flags=cv2.SOLVEPNP_SQPNP,
        )

    best_ret = None

    # If the solver found solutions, filter them for physical plausibility
    if ret and len(rvecs) > 0:
        logging.info(f"Extrinsics: Solver found {len(rvecs)} solutions.")

        candidates = []
        for i in range(len(rvecs)):
            rv, tv = rvecs[i], tvecs[i]
            rmat, _ = cv2.Rodrigues(rv)
            cc = -(rmat.T @ tv.flatten())

            proj, _ = cv2.projectPoints(
                object_points, rv, tv, camera_matrix, distortion_coefficients
            )
            err = np.mean(np.linalg.norm(image_points - proj.reshape(-1, 2), axis=1))

            candidates.append({"rv": rv, "tv": tv, "cc": cc, "err": err, "index": i})
            logging.info(f"  Sol {i}: cc_z={cc[2]:.1f}, tv_z={tv[2][0]:.1f}, err={err:.2f}")

        # Selection Strategy:
        # 1. MUST have tz > 0 (Points in front of camera)
        # 2. Prefer cc_z > 0 (Camera above table) if both sides are equally good.
        # 3. BUT, if only cc_z < 0 is found, accept it to avoid failure (Z-down system).

        # Sort candidates by error
        candidates.sort(key=lambda x: x["err"])

        # Pass 1: Strict (Above table AND in front)
        for c in candidates:
            if c["cc"][2] > 0 and c["tv"][2] > 0:
                best_ret = (c["rv"], c["tv"])
                logging.info(f"Extrinsics: Selected Above-Table solution (err={c['err']:.2f})")
                break

        # Pass 2: Fallback (Below-Table AND in front)
        if not best_ret:
            for c in candidates:
                if c["tv"][2] > 0:
                    best_ret = (c["rv"], c["tv"])
                    logging.info(f"Extrinsics: Selected Below-Table solution (err={c['err']:.2f})")
                    break

    if best_ret:
        rotation_vector, translation_vector = best_ret
        return rotation_vector, translation_vector, object_points, image_points

    return None


def calibrate_projector_3d(
    correspondences: list[tuple[np.ndarray, np.ndarray]],
    projector_resolution: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float] | None:
    """
    Estimates projector intrinsics and extrinsics from 3D-to-2D correspondences.

    Args:
        correspondences: List of (3D point, 2D point) pairs.
        projector_resolution: (width, height) of the projector.

    Returns:
        (intrinsic_matrix, distortion_coefficients, rotation_vector, translation_vector, rms)
    """
    logging.info("Projector3DCalibrationScene: Starting solvePnP for 3D projector calibration.")

    # Extract points
    object_points = np.array([pair[0] for pair in correspondences], dtype=np.float32)
    image_points = np.array([pair[1] for pair in correspondences], dtype=np.float32)

    # We need a minimum number of points for stability
    if len(object_points) < 10:
        logging.error("calibrate_projector_3d: Not enough points (need at least 10 for stability, got %d).", len(object_points))
        return None

    # Initial guess for intrinsics: focal lengths = resolution
    # This is a much better starting point for the solver.
    intrinsic_matrix = np.array(
        [[projector_resolution[0], 0, projector_resolution[0] / 2],
         [0, projector_resolution[1], projector_resolution[1] / 2],
         [0, 0, 1]], dtype=np.float32
    )
    distortion_coefficients = np.zeros(5, dtype=np.float32)

    # Solver: SQPNP is robust to non-planar configurations.
    # Since these are 3D points, we use solvePnPGeneric.
    # This will find the R and t that best match the correspondences given the initial K.
    ret, rvecs, tvecs, errs = cv2.solvePnPGeneric(
        object_points,
        image_points,
        intrinsic_matrix,
        distortion_coefficients,
        flags=cv2.SOLVEPNP_SQPNP,
    )

    if not ret or len(rvecs) == 0:
        logging.error("calibrate_projector_3d: Solver failed to find a solution.")
        return None

    # Pick best solution (smallest error)
    best_idx = -1
    min_err = float("inf")
    for i, err in enumerate(errs):
        if err < min_err:
            min_err = err
            best_idx = i

    rotation_vector = rvecs[best_idx]
    translation_vector = tvecs[best_idx]

    # Now that we have a decent R and t, we can refine K.
    # The 3D points (X, Y, Z) are in world space.
    # The camera's rotation and translation define the mapping from world to camera.
    # We want to find K such that for each point:
    # image_pixels = K * [R * world_point + t]
    # Since R and t are known, we can project the 3D points to the camera frame.

    rmat, _ = cv2.Rodrigues(rotation_vector)
    # camera_center_world = -R^T * t
    camera_center_world = (-rmat.T @ translation_vector).flatten()

    # We can use a simple iterative approach or just a linear solve.
    # Let's try a simple iterative refinement:
    for _ in range(10):
        # Project the 3D points using current R, t, and K
        # Note: we use the world_point directly because we want to find K
        # that maps world_point -> image_pixels
        # However, solvePnPGeneric assumes the 3D points are in the CAMERA frame.
        # Our object_points are in WORLD frame.
        # Let's convert them to camera frame.
        points_in_camera = (rmat @ object_points.T + translation_vector.reshape(3, 1)).T

        # Now we have (X_c, Y_c, Z_c) and (u, v).
        # u = fx * (X_c / Z_c) + cx
        # v = fy * (Y_c / Z_c) + cy
        # Since we want to find K = [fx, 0, cx; 0, fy, cy; 0, 0, 1]
        # We can use least squares:
        # fx = sum((u - cx) * (X_c / Z_c)) / sum((X_c / Z_c)^2)
        # fy = sum((v - cy) * (Y_c / Z_c)) / sum((Y_c / Z_c)^2)

        cx = projector_resolution[0] / 2
        cy = projector_resolution[1] / 2

        # Avoid division by zero
        mask = points_in_camera[:, 2] > 0.1
        points_c = points_in_camera[mask]

        x_c_over_z_c = points_c[:, 0] / points_c[:, 2]
        y_c_over_z_c = points_c[:, 1] / points_c[:, 2]

        fx = np.sum((image_points[mask, 0] - cx) * x_c_over_z_c) / (np.sum(x_c_over_z_c**2) + 1e-6)
        fy = np.sum((image_points[mask, 1] - cy) * y_c_over_z_c) / (np.sum(y_c_over_z_c**2) + 1e-6)

        # Update K
        intrinsic_matrix[0, 0] = fx
        intrinsic_matrix[1, 1] = fy
        intrinsic_matrix[0, 2] = cx
        intrinsic_matrix[1, 2] = cy

        logging.info("Refinement Iteration: fx=%.2f, fy=%.2f, cx=%.2f, cy=%.2f", fx, fy, cx, cy)

    # Final solve to get the best R, t for the refined K
    ret, rvecs, tvecs, errs = cv2.solvePnPGeneric(
        object_points,
        image_points,
        intrinsic_matrix,
        distortion_coefficients,
        flags=cv2.SOLVEPNP_SQPNP,
    )
    
    if not ret or len(rvecs) == 0:
        return None

    best_idx = -1
    min_err = float("inf")
    for i, err in enumerate(errs):
        if err < min_err:
            min_err = err
            best_idx = i

    rotation_vector = rvecs[best_idx]
    translation_vector = tvecs[best_idx]

    logging.info("Projector3DCalibrationScene: Final solved K: [%.1f, %.1f]", fx, fy)
    logging.info("Projector3DCalibrationScene: Final solved R: [%.2f, %.2f, %.2f], t: [%.2f, %.2f, %.2f], RMS: %.4f", rotation_vector.flatten(), translation_vector.flatten(), min_err)

    return (
        intrinsic_matrix,
        distortion_coefficients,
        rotation_vector,
        translation_vector,
        min_err,
    )
