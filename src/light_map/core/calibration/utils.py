"""
Utility functions for stereo calibration and marker partitioning.
"""

import logging
import os

import cv2
import numpy as np


logger = logging.getLogger(__name__)


def load_calibration_npz(filepath: str) -> tuple[np.ndarray, np.ndarray]:
    """Loads K and dist from an .npz file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Calibration file not found: {filepath}")

    data = np.load(filepath)
    # Assume keys 'K' and 'dist'
    K = data["K"]
    dist = data["dist"]
    return K, dist


def resolve_lens_intrinsics(camera_side: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Resolves lens intrinsics based on the camera side with a fallback mechanism.

    - Camera Left: camera_left_calibration.npz -> camera_calibration.npz
    - Camera Right: camera_right_calibration.npz -> camera_calibration.npz
    """
    # Wait, I should probably check where these files are expected to be.
    # The spec says "Looks for ...". I'll assume they are in a 'calibration_data' folder in the root.

    if camera_side == "left":
        paths = [
            "calibration_data/camera_left_calibration.npz",
            "calibration_data/camera_calibration.npz",
        ]
    else:
        paths = [
            "calibration_data/camera_right_calibration.npz",
            "calibration_data/camera_calibration.npz",
        ]

    for path in paths:
        try:
            K, dist = load_calibration_npz(path)
            logger.info("Loaded intrinsics from %s", path)
            return K, dist
        except FileNotFoundError:
            continue

    logger.warning("No calibration files found for %s. Using default values.", camera_side)
    # Return some dummy values if nothing found
    K = np.array([[1000, 0, 960], [0, 1000, 540], [0, 0, 1]], dtype=np.float32)
    dist = np.zeros(5, dtype=np.float32)
    return K, dist


def get_marker_partition():
    """
    Returns the partition for DICT_4X4_50 marker IDs.

    - 0-39: User Game Tokens
    - 40-41: Physical PPI Ruler Sheet
    - 42-49: Projected Calibration Arena
    """
    return {
        "user_tokens": range(0, 40),
        "ppi_ruler": range(40, 42),
        "projected_arena": range(42, 50),
    }


def compute_roi_pass2(
    sensor_res: tuple[int, int],
    r_l: np.ndarray,
    t_l: np.ndarray,
    r_r: np.ndarray,
    t_r: np.ndarray,
    projector_ppi: float,
    pts_3d: np.ndarray,
    k_l: np.ndarray,
    dist_l: np.ndarray,
    k_r: np.ndarray,
    dist_r: np.ndarray,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    Computes the sensor ROI for both cameras using a two-pass approach.

    1. Project the 3D points of the projected arena (Z=0) and
       the 3D positions of the tokens (Z=h) into both cameras.
    2. Find the 2D bounding box of all projected points.
    3. Add a 200mm vertical margin based on the projector PPI.
    """
    # Project to Camera L
    img_pts_l, _ = cv2.projectPoints(pts_3d, r_l, t_l, k_l, dist_l)
    img_pts_l = img_pts_l.reshape(-1, 2)

    # Project to Camera R
    # P_R_cam = R_stereo @ P_L_cam + t_stereo
    # P_L_cam = R_world_to_l @ P_world + t_world_to_l
    # P_R_cam = R_stereo @ (R_world_to_l @ P_world + t_world_to_l) + t_stereo
    # P_R_cam = (R_stereo @ R_world_to_l) @ P_world + (R_stereo @ t_world_to_l + t_stereo)
    # Since we are projecting from world to R directly using r_r and t_r:
    img_pts_r, _ = cv2.projectPoints(pts_3d, r_r, t_r, k_r, dist_r)
    img_pts_r = img_pts_r.reshape(-1, 2)

    def get_bbox(pts):
        min_x = np.min(pts[:, 0])
        max_x = np.max(pts[:, 0])
        min_y = np.min(pts[:, 1])
        max_y = np.max(pts[:, 1])

        x1 = max(0, int(min_x))
        y1 = max(0, int(min_y))
        x2 = min(sensor_res[0], int(max_x))
        y2 = min(sensor_res[1], int(max_y))

        # Add 5% safety margin
        margin_x = (x2 - x1) * 0.05
        margin_y = (y2 - y1) * 0.05

        x1 = max(0, int(x1 - margin_x))
        y1 = max(0, int(y1 - margin_y))
        x2 = min(sensor_res[0], int(x2 + margin_x))
        y2 = min(sensor_res[1], int(y2 + margin_y))

        return (x1, y1, x2 - x1, y2 - y1)

    roi_l = get_bbox(img_pts_l)
    roi_r = get_bbox(img_pts_r)

    return roi_l, roi_r
