import logging
import os

import numpy as np


def load_lens_profiles(camera_side: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Loads camera matrix and distortion coefficients with fallback resolution.

    Args:
        camera_side: "left" or "right"

    Returns:
        Tuple of (camera_matrix, distortion_coefficients)
    """
    if camera_side == "left":
        files = ["camera_left_calibration.npz", "camera_calibration.npz"]
    elif camera_side == "right":
        files = ["camera_right_calibration.npz", "camera_calibration.npz"]
    else:
        raise ValueError("camera_side must be 'left' or 'right'")

    for file_name in files:
        # Try to find file in the current directory or in data paths
        # For now, we check current directory as per convention in other scenes
        if os.path.exists(file_name):
            data = np.load(file_name)
            camera_matrix = data["camera_matrix"]
            distortion_coefficients = data["distortion_coefficients"]
            logging.info(f"Loaded {camera_side} lens profile from {file_name}")
            return camera_matrix, distortion_coefficients

    logging.warning(f"Could not find any lens profile for {camera_side}. Using identity matrix.")
    return np.eye(3), np.zeros(5)


def solve_stereo_extrinsics(
    left_points: np.ndarray,
    right_points: np.ndarray,
    left_intrinsics: tuple[np.ndarray, np.ndarray],
    right_intrinsics: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculates the relative transform between the left and right cameras.

    Args:
        left_points: 3D points in left camera's coordinate system.
        right_points: 3D points in right camera's coordinate system.
        left_intrinsics: (matrix, dist) for left camera.
        right_intrinsics: (matrix, dist) for right camera.

    Returns:
        Tuple of (R_stereo, T_stereo)
    """
    # Implementation to be filled
    pass


def solve_table_homography(
    projector_matrix: np.ndarray, grid_points_projector: np.ndarray, grid_points_camera: np.ndarray
) -> np.ndarray:
    """
    Solves for the tabletop homography by finding the world coordinates of the grid points.
    Since the grid points are on the table (Z=0), we can solve the 2x2 system:
    P[:2, :2] * [X, Y]^T = [x_p - P[0, 3], y_p - P[1, 3]]^T
    where P is the projector matrix and (x_p, y_p) are the points in the projector image.
    """
    world_points = []
    for i in range(len(grid_points_projector)):
        x_p, y_p = grid_points_projector[i]
        A = projector_matrix[:2, :2]
        b = np.array([x_p - projector_matrix[0, 3], y_p - projector_matrix[1, 3]])
        try:
            res = np.linalg.solve(A, b)
            world_points.append([res[0], res[1], 0.0])
        except np.linalg.LinAlgError:
            res, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
            world_points.append([res[0], res[1], 0.0])

    return np.array(world_points)


def solve_non_planar_extrinsics(
    token_points_camera: np.ndarray,
    token_points_projector: np.ndarray,
    token_heights: dict[int, float],
    ppi: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Solves for rigid extrinsics using non-planar points (tokens with height).
    """
    # Implementation to be filled
    pass


def calculate_roi(
    left_intrinsics: tuple[np.ndarray, np.ndarray],
    right_intrinsics: tuple[np.ndarray, np.ndarray],
    rotation_vector: np.ndarray,
    translation_vector: np.ndarray,
    projector_matrix: np.ndarray,
    ppi: float,
    table_corners_projector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculates the 2D bounding envelope for sensor ROIs with 200mm parallax margin.
    """
    # Implementation to be filled
    pass
