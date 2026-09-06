import numpy as np
import cv2
from typing import List, Tuple

def calculate_roi(
    camera_matrix_l: np.ndarray,
    distortion_coefficients_l: np.ndarray,
    camera_matrix_r: np.ndarray,
    distortion_coefficients_r: np.ndarray,
    grid_corners_world: np.ndarray,
    grid_corners_l: np.ndarray,
    grid_corners_r: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculates the 2D sensor ROIs for both cameras based on the 3D tabletop grid
    and a 200mm parallax margin.
    """
    # Grid corners are in world space (mm)
    # We want to project both the Z=0 (tabletop) and Z=200 (max height) points
    # to find the bounding envelope.
    
    # Project Z=0 points
    pts_l_0 = cv2.projectPoints(grid_corners_world, camera_matrix_l, distortion_coefficients_l, (None, None))
    pts_r_0 = cv2.projectPoints(grid_corners_world, camera_matrix_r, distortion_coefficients_r, (None, None))
    
    # Project Z=200 points (simulated by adding 200 to the Z component)
    grid_corners_200 = grid_corners_world.copy()
    grid_corners_200[:, 2] += 200.0
    
    pts_l_200 = cv2.projectPoints(grid_corners_200, camera_matrix_l, distortion_coefficients_l, (None, None))
    pts_r_200 = cv2.projectPoints(grid_corners_200, camera_matrix_r, distortion_coefficients_r, (None, None))
    
    # Combine all projected points for each camera
    all_pts_l = np.vstack((pts_l_0, pts_l_200))
    all_pts_r = np.vstack((pts_r_0, pts_r_200))
    
    # Find bounding box
    min_x_l, min_y_l = np.min(all_pts_l, axis=0)
    max_x_l, max_y_l = np.max(all_pts_l, axis=0)
    
    min_x_r, min_y_r = np.min(all_pts_r, axis=0)
    max_x_r, max_y_r = np.max(all_pts_r, axis=0)
    
    # Add 5% safety margin
    width_l = max_x_l - min_x_l
    height_l = max_y_l - min_y_l
    margin_l = width_l * 0.05
    
    width_r = max_x_r - min_x_r
    height_r = max_y_r - min_y_r
    margin_r = width_r * 0.05
    
    roi_l = [
        min_x_l - margin_l,
        min_y_l - margin_l,
        max_x_l + margin_l,
        max_y_l + margin_l
    ]
    
    roi_r = [
        min_x_r - margin_r,
        min_y_r - margin_r,
        max_x_r + margin_r,
        max_y_r + margin_r
    ]
    
    return np.array(roi_l), np.array(roi_r)
