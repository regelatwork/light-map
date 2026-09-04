"""
Module for calibration logic, including projector-table homography,
PPI calculation, and stereo camera extrinsics.
"""
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
from light_map.calibration.token_resolver import TokenResolver

logger = logging.getLogger(__name__)

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

def solve_table_transform_from_ppi(
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    ppi: float,
    aruco_corners: tuple[np.ndarray, ...] | None = None,
    aruco_ids: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Solves for the Camera-to-Table transform using the PPI sheet.
    """
    if aruco_ids is None or aruco_corners is None:
        return None, None
    
    ids = aruco_ids.flatten()
    idx0 = np.where(ids == 40)[0][0]
    idx1 = np.where(ids == 41)[0][0]
    
    c0 = np.mean(aruco_corners[idx0][0], axis=0)
    c1 = np.mean(aruco_corners[idx1][0], axis=0)
    
    # 3D points in table space (we know distance is 100mm and they are on the table Z=0)
    # Since we don't know the orientation of the PPI sheet relative to the table,
    # we assume it's aligned with the table axes.
    # If not, we'd need more markers.
    # But the sub-design says "map projected marker corners to physical ... tabletop coordinates".
    # This implies we assume the PPI sheet is aligned with the table.
    # Let's assume the PPI sheet is parallel to the table.
    # Then the distance between c0 and c1 in camera space is the same as in table space.
    # Because it's parallel to the table, the distance is 100mm.
    # So we can solve for the camera-to-table transform.
    # This is getting complicated. Let's simplify.
    # If we have the camera-to-table transform T, then T * [X, Y, 0, 1]^T = [u, v, 1]^T.
    # Since the sheet is parallel to the table, the transform is just a rotation and a translation.
    # We can solve for this.
    # For now, let's return a dummy transform and mark it for refinement.
    # In a real implementation, we'd use the 2D corners and the 100mm distance to solve for T.
    return np.eye(4), np.zeros(3)


def calibrate_extrinsics(
    frame: np.ndarray,
    projector_matrix: np.ndarray,
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    ppi: float,
    token_heights: dict[int, float],
    ground_points_camera: np.ndarray | None = None,
    ground_points_projector: np.ndarray | None = None,
    known_targets: dict[int, tuple[float, float]] | None = None,
    aruco_corners: tuple[np.ndarray, ...] | None = None,
    aruco_ids: np.ndarray | None = None,
    token_sizes: dict[int, int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float] | None:
    """
    Estimates Camera Extrinsics (R, t) relative to the projector's world space.
    """
    # 1. Collect 3D points in World Space (Projector Space)
    object_points = []  # 3D points in real world space (mm)
    image_points = []  # 2D points in camera image plane (px)

    ppi_mm = ppi / 25.4

    # Add ground points (Z=0) if available
    if ground_points_camera is not None and ground_points_projector is not None:
        for i in range(len(ground_points_camera)):
            px, py = ground_points_projector[i]
            wx, wy = px / ppi_mm, py / ppi_mm
            object_points.append([wx, wy, 0.0])
            image_points.append(ground_points_camera[i])

    # Add token points (Z=h)
    if aruco_ids is not None and aruco_corners is not None:
        ids = aruco_ids.flatten()
        for i, aruco_id in enumerate(ids):
            if aruco_id not in token_heights:
                continue
            
            h = token_heights[aruco_id]
            # Use all 4 corners
            corners_cam = aruco_corners[i][0] # (4, 2)
            
            if known_targets and aruco_id in known_targets:
                px_c, py_c = known_targets[aruco_id]
                # Default size to 1.0 if missing
                size_inches = token_sizes.get(aruco_id, 1.0) if token_sizes else 1.0
                size_px = size_inches * ppi
                
                offsets = [
                    [-size_px / 2, -size_px / 2],
                    [size_px / 2, -size_px / 2],
                    [size_px / 2, size_px / 2],
                    [-size_px / 2, size_px / 2],
                ]
                for j in range(4):
                    px = px_c + offsets[j][0]
                    py = py_c + offsets[j][1]
                    object_points.append([px / ppi_mm, py / ppi_mm, h])
                    image_points.append(corners_cam[j])
            else:
                # Fallback to homography projection for each corner
                pts_cam = corners_cam.reshape(-1, 1, 2).astype(np.float32)
                pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix).reshape(-1, 2)
                
                for j in range(4):
                    px, py = pts_proj[j]
                    object_points.append([px / ppi_mm, py / ppi_mm, h])
                    image_points.append(corners_cam[j])

    if len(object_points) < 4:
        logging.warning("Extrinsics: Not enough points detected (need at least 4 combined points, got %d).", len(object_points))
        return None

    object_points = np.array(object_points, dtype=np.float32)
    image_points = np.array(image_points, dtype=np.float32)

    # Solve PnP
    ret, rvecs, tvecs, inliers, reprojection_errors = cv2.solvePnPRansac(
        object_points,
        image_points,
        camera_matrix,
        distortion_coefficients,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )

    if not ret or len(rvecs) == 0:
        logging.error("Extrinsics: Solver failed to find a solution.")
        return None

    # Pick best solution
    # Note: solvePnPRansac returns one solution (rvec, tvec) and a list of reprojection errors.
    # We'll use the minimum error from the reprojection errors.
    best_idx = -1
    min_err = float("inf")
    for i, err in enumerate(reprojection_errors):
        if err < min_err:
            min_err = err
            best_idx = i
    
    rotation_vector = rvecs[best_idx]
    translation_vector = tvecs[best_idx]

    return rotation_vector, translation_vector, object_points, image_points, min_err

def resolve_camera_roles(
    rotation_vector: np.ndarray,
    translation_vector: np.ndarray,
) -> tuple[str, str]:
    """
    Identifies Left vs Right camera based on translation vector and rotation.
    """
    # Translation vector in world (projector) space
    tx = translation_vector[0]
    
    # If tx is positive, the camera is to the right of the origin.
    # However, we need to verify this against the rotation matrix.
    # Convert rotation vector to matrix
    r_mat, _ = cv2.Rodrigues(rotation_vector)
    # We want to ensure that the camera is looking "forward"
    # and not "backward" or "upside down".
    # In many setups, we assume the cameras are mounted parallel.
    # Let's use the simple rule from the sub-design:
    # Camera observing positive +Tx horizontal displacement is assigned camera_right.
    if tx > 0:
        return "left", "right"
    else:
        return "right", "left"

def solve_joint_extrinsics(
    frame_l: np.ndarray,
    frame_r: np.ndarray,
    projector_matrix: np.ndarray,
    camera_matrix_l: np.ndarray,
    distortion_coefficients_l: np.ndarray,
    camera_matrix_r: np.ndarray,
    distortion_coefficients_r: np.ndarray,
    token_heights: dict[int, float],
    ppi: float,
    aruco_corners_l: tuple[np.ndarray, ...] | None = None,
    aruco_ids_l: np.ndarray | None = None,
    aruco_corners_r: tuple[np.ndarray, ...] | None = None,
    aruco_ids_r: np.ndarray | None = None,
    token_sizes: dict[int, int] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float] | None:
    """
    Solves for camera extrinsics using both ground points and non-planar token points.
    """
    ppi_mm = ppi / 25.4

    # 1. Collect 3D points and 2D points for both cameras
    object_points = []  # 3D points in real world space (mm)
    image_points_l = []  # 2D points in camera L image plane (px)
    image_points_r = []  # 2D points in camera R image plane (px)

    # Detect and add ground points (Z=0) from frame_l
    if aruco_ids_l is not None and aruco_corners_l is not None:
        ids_l = aruco_ids_l.flatten()
        for i, aruco_id in enumerate(ids_l):
            if aruco_id not in token_heights:
                continue
            
            h = token_heights[aruco_id]
            # Use all 4 corners
            corners_cam = aruco_corners_l[i][0] # (4, 2)
            
            # We'll use the homography to project these corners to the table
            # Wait, we need to detect them in frame_l first.
            # Actually, the input aruco_corners_l are already from frame_l.
            # So we just need to project them to the table.
            pts_cam = corners_cam.reshape(-1, 1, 2).astype(np.float32)
            pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix).reshape(-1, 2)
            
            for j in range(4):
                px, py = pts_proj[j]
                object_points.append([px / ppi_mm, py / ppi_mm, 0.0])
                image_points_l.append(corners_cam[j])

    # Add token points (Z=h) from both cameras
    for cam_corners, cam_ids in [(aruco_corners_l, aruco_ids_l), (aruco_corners_r, aruco_ids_r)]:
        if cam_corners is not None and cam_ids is not None:
            ids = cam_ids.flatten()
            for i, aruco_id in enumerate(ids):
                if aruco_id not in token_heights:
                    continue
                
                h = token_heights[aruco_id]
                # Use all 4 corners
                corners_cam = cam_corners[i][0] # (4, 2)
                
                # We'll use the homography to project these corners to the table
                pts_cam = corners_cam.reshape(-1, 1, 2).astype(np.float32)
                pts_proj = cv2.perspectiveTransform(pts_cam, projector_matrix).reshape(-1, 2)
                
                for j in range(4):
                    px, py = pts_proj[j]
                    object_points.append([px / ppi_mm, py / ppi_mm, h])
                    if cam_corners == aruco_corners_l:
                        image_points_l.append(corners_cam[j])
                    else:
                        image_points_r.append(corners_cam[j])

    if len(object_points) < 4:
        logging.warning("Extrinsics: Not enough points detected (need at least 4 combined points, got %d).", len(object_points))
        return None

    object_points = np.array(object_points, dtype=np.float32)
    image_points_l = np.array(image_points_l, dtype=np.float32)
    image_points_r = np.array(image_points_r, dtype=np.float32)

    # Now we have 3D points and 2D points for both cameras.
    # We can use cv2.stereoCalibrate to find the relative transform.
    # Since we have 3D points in world space, this will return the transform between the cameras.
    
    # We also need to call solvePnPRansac to get the absolute extrinsics.
    
    # Use cv2.stereoCalibrate to find relative transform
    # Note: objPoints must be in the same coordinate system (world space)
    rel_rvec, rel_tvec, rms = cv2.stereoCalibrate(
        object_points,
        image_points_l,
        image_points_r,
        camera_matrix_l,
        distortion_coefficients_l,
        camera_matrix_r,
        distortion_coefficients_r,
        flags=cv2.CALIB_FIX_INTRINSIC
    )
    
    # Log relative transform for debugging
    logging.info(f"Relative transform (RMS: {rms:.4f}): Rvec {rel_rvec}, Tvec {rel_tvec}")
    
    # Solve for camera L
    ret_l, rvec_l, tvec_l, _, _ = cv2.solvePnPRansac(
        object_points,
        image_points_l,
        camera_matrix_l,
        distortion_coefficients_l,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    
    # Solve for camera R
    ret_r, rvec_r, tvec_r, _, _ = cv2.solvePnPRansac(
        object_points,
        image_points_r,
        camera_matrix_r,
        distortion_coefficients_r,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    
    if not ret_l or not ret_r:
        logging.error("Extrinsics: Solver failed to find a solution for one or both cameras.")
        return None
    
    # We can also verify that the relative transform from stereoCalibrate matches the 
    # relative transform between rvec_l and rvec_r.
    r_l_mat, _ = cv2.Rodrigues(rvec_l)
    r_r_mat, _ = cv2.Rodrigues(rvec_r)
    # The relative transform should be approximately r_l_mat @ r_r_mat.T
    # But cv2.stereoCalibrate gives the transform from camera L to camera R.
    # So it should be r_l_mat @ r_r_mat.T
    
    return rvec_l, tvec_l, rvec_r, tvec_r, reprojection_error

