"""
Module for computing sensor ROIs based on 3D parallax volume.
"""

import numpy as np


def compute_roi_pass1(
    image_shape: tuple[int, int], markers: list[tuple[int, np.ndarray]]
) -> tuple[int, int, int, int]:
    """
    Pass 1: Uncalibrated Bounds.
    Returns the initial bounding box of the projected table by finding the
    boundary of the projected grid markers (IDs 42-47).
    """
    if not markers:
        return 0, 0, image_shape[0], image_shape[1]

    grid_ids = list(range(42, 50))
    grid_corners = []
    for m_id, corners in markers:
        if m_id in grid_ids:
            grid_corners.append(corners)

    if not grid_corners:
        return 0, 0, image_shape[0], image_shape[1]

    pts = np.array(grid_corners).reshape(-1, 2)
    min_x, min_y = np.min(pts, axis=0)
    max_x, max_y = np.max(pts, axis=0)

    # Add a small margin (e.g., 20mm) for the grid
    # Since we don't know the scale yet, we'll add a percentage margin.
    margin_x = (max_x - min_x) * 0.1
    margin_y = (max_y - min_y) * 0.1

    x1 = max(0, int(min_x - margin_x))
    y1 = max(0, int(min_y - margin_y))
    x2 = min(image_shape[1], int(max_x + margin_x))
    y2 = min(image_shape[0], int(max_y + margin_y))

    return x1, y1, x2 - x1, y2 - y1


def compute_roi_pass2(
    image_shape: tuple[int, int],
    r_left: np.ndarray,
    t_left: np.ndarray,
    r_right: np.ndarray,
    t_right: np.ndarray,
    max_height_mm: float = 200.0,
    corners_3d: np.ndarray = None,
    k_left: np.ndarray = None,
    k_right: np.ndarray = None,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    Pass 2: 3D Parallax Volume Envelope.
    Projects 4 corners at Z=0 and Z=max_height_mm and finds the 2D bounding box.
    """
    if corners_3d is None:
        # Default to 2m x 2m centered at 0,0,0 in mm.
        corners_3d = np.array(
            [[-1000, -1000, 0.0], [1000, -1000, 0.0], [1000, 1000, 0.0], [-1000, 1000, 0.0]],
            dtype=np.float32,
        )
    else:
        corners_3d = np.array(corners_3d, dtype=np.float32)
    corners_3d_max = corners_3d.copy()
    corners_3d_max[:, 2] = max_height_mm * 1.05
    all_corners_3d = np.vstack([corners_3d, corners_3d_max])

    def project_points(points_3d, r, t, k):
        K = k if k is not None else np.eye(3)
        hom_points = np.hstack([points_3d, np.ones((points_3d.shape[0], 1))])
        t_hom = t.reshape(3, 1)
        p_cam = (np.hstack([r, t_hom]) @ hom_points.T).T
        # Discard points behind or too close to camera plane (Z_cam <= 10.0mm)
        valid = p_cam[:, 2] > 10.0
        if not np.any(valid):
            return np.zeros((0, 2), dtype=np.float32)
        projected = (K @ p_cam[valid].T).T
        projected_2d = projected[:, :2] / projected[:, 2:3]
        return projected_2d

    # Project points for both cameras
    pts_l = project_points(all_corners_3d, r_left, t_left, k_left)
    pts_r = project_points(all_corners_3d, r_right, t_right, k_right)

    def get_bbox(pts, img_w, img_h):
        if pts.shape[0] == 0:
            return (0, 0, img_w, img_h)
        min_x = np.min(pts[:, 0])
        max_x = np.max(pts[:, 0])
        min_y = np.min(pts[:, 1])
        max_y = np.max(pts[:, 1])

        # Clip to image boundaries
        x1 = max(0, int(min_x))
        y1 = max(0, int(min_y))
        x2 = min(img_w, int(max_x))
        y2 = min(img_h, int(max_y))

        # Add 5% safety margin
        margin_x = (x2 - x1) * 0.05
        margin_y = (y2 - y1) * 0.05

        x1 = max(0, int(x1 - margin_x))
        y1 = max(0, int(y1 - margin_y))
        x2 = min(img_w, int(x2 + margin_x))
        y2 = min(img_h, int(y2 + margin_y))

        return (x1, y1, x2 - x1, y2 - y1)

    roi_l = get_bbox(pts_l, image_shape[1], image_shape[0])
    roi_r = get_bbox(pts_r, image_shape[1], image_shape[0])

    return roi_l, roi_r
