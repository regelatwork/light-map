import cv2
import numpy as np
from typing import Tuple


def generate_calibration_pattern(
    width, height, pattern_rows, pattern_cols, border_size=100
):
    """
    Generates a visual calibration pattern (checkerboard).

    Args:
        width: Total width of the screen/image.
        height: Total height of the screen/image.
        pattern_rows: Number of rows in the pattern.
        pattern_cols: Number of columns in the pattern.
        border_size: Padding around the pattern.

    Returns:
        pattern_image: The generated image.
        pattern_params: Dict containing metadata like square size (pixels), offsets, etc.
    """
    # Calculate square size based on available space and requested rows/cols
    max_sq_w = (width - 2 * border_size) // pattern_cols
    max_sq_h = (height - 2 * border_size) // pattern_rows
    square_size = min(max_sq_w, max_sq_h)

    pattern_image = np.zeros((height, width, 3), dtype=np.uint8)
    pattern_image.fill(255)  # White background

    # Calculate starting position to center the pattern
    total_pattern_w = square_size * pattern_cols
    total_pattern_h = square_size * pattern_rows

    start_x = (width - total_pattern_w) // 2
    start_y = (height - total_pattern_h) // 2

    for i in range(pattern_rows):
        for j in range(pattern_cols):
            x1 = start_x + j * square_size
            y1 = start_y + i * square_size
            x2 = start_x + (j + 1) * square_size
            y2 = start_y + (i + 1) * square_size

            if (i + j) % 2 == 0:
                color = (0, 0, 0)
            else:
                color = (255, 255, 255)

            cv2.rectangle(pattern_image, (x1, y1), (x2, y2), color, -1)

    return pattern_image, {
        "square_size": square_size,
        "border_size": border_size,
        "start_x": start_x,
        "start_y": start_y,
        "rows": pattern_rows,
        "cols": pattern_cols,
    }


def compute_projector_homography(
    camera_image, pattern_params, camera_matrix=None, distortion_coefficients=None
):
    """
    Computes the homography matrix to map camera coordinates to projector coordinates.

    Args:
        camera_image: The image captured by the camera showing the projected pattern.
        pattern_params: Metadata from generate_calibration_pattern.

    Returns:
        transformation_matrix: 3x3 homography matrix.
    """
    gray = cv2.cvtColor(camera_image, cv2.COLOR_BGR2GRAY)

    # Inner corners are (rows-1, cols-1)
    # Note: cv2.findChessboardCorners expects (cols, rows)
    board_size = (pattern_params["cols"] - 1, pattern_params["rows"] - 1)

    ret, corners = cv2.findChessboardCorners(gray, board_size, None)

    if not ret:
        raise RuntimeError("Chessboard pattern not detected in the captured image.")

    # Prepare screen points (where we drew the corners)
    # The corners correspond to the intersections of the squares.
    screen_points = []

    sq_size = pattern_params["square_size"]
    start_x = pattern_params.get("start_x", pattern_params.get("border_size", 0))
    start_y = pattern_params.get("start_y", pattern_params.get("border_size", 0))

    # The loop order must match the order findChessboardCorners returns (row by row, left to right)
    for i in range(board_size[1]):  # rows
        for j in range(board_size[0]):  # cols
            # The first inner corner is at the bottom-right of the first square (0,0)
            # if we consider (0,0) to be top-left square.
            # Actually, (0,0) square is at x=border, y=border.
            # Its bottom-right corner is at x=border+100, y=border+100.
            # So coordinate is (j+1)*sq_size + border

            # Original code logic:
            # screen_points[i * ... + j] = [j * 100 + 50 + border, i * 100 + 50 + border]
            # Wait, the original code added 50? That puts it in the *center* of the square?
            # cv2.findChessboardCorners finds *internal corners* (intersections).
            # If the original code used centers, that might be a misunderstanding of findChessboardCorners,
            # OR they were detecting blobs/circles?
            # Re-reading original code:
            # ret, corners = cv2.findChessboardCorners(...)
            # screen_points... = [j * 100 + 50 + border_size, i * 100 + 50 + border_size]

            # If they drew squares of size 100 starting at border_size.
            # The first intersection is at (border + 100, border + 100).
            # The original code puts the target point at (border + 50, border + 50)?
            # That is the center of the first top-left square.
            # findChessboardCorners finds the *intersections*.

            # Correction: If the user wants to map the *detected corner* to a specific *screen pixel*,
            # and findChessboardCorners returns intersections, then screen_points MUST be the pixel coordinates
            # of those intersections on the generated image.

            # Intersection (0,0) corresponds to the point between square(0,0), (0,1), (1,0), (1,1).
            # x = border + 1 * square_size
            # y = border + 1 * square_size

            # The original code seems to be mapping the detected corner to the *center* of the square.
            # This is mathematically incorrect for standard chessboard calibration if they are using findChessboardCorners.
            # However, I should probably stick to a Correct implementation or replicate the behavior if it was intentional?
            # Given the original code was likely "experimental", I will implement the STANDARD correct mapping:
            # Mapping detected corners to the grid intersections.

            x = start_x + (j + 1) * sq_size
            y = start_y + (i + 1) * sq_size
            screen_points.append([x, y])

    screen_points = np.array(screen_points, dtype=np.float32)
    camera_points = corners.reshape(-1, 2)

    # Compute homography
    transformation_matrix, _ = cv2.findHomography(camera_points, screen_points)

    return transformation_matrix, camera_points, screen_points


class ProjectorDistortionModel:
    """
    Handles non-linear correction for projector distortion (barrel/keystone)
    by interpolating residuals from a calibration grid.
    """

    def __init__(
        self,
        homography: np.ndarray,
        camera_points: np.ndarray,
        projector_points: np.ndarray,
    ):
        self.homography = homography
        self.camera_points = camera_points
        self.projector_points = projector_points

        # 1. Calculate theoretical points for each camera point
        src_pts = camera_points.reshape(-1, 1, 2)
        theoretical = cv2.perspectiveTransform(src_pts, homography).reshape(-1, 2)

        # 2. Calculate residuals (Actual - Theoretical)
        # We define residuals in PROJECTOR (Screen) Space
        self.residuals = projector_points - theoretical

        # 3. Organize into a grid for faster lookup
        # We assume the camera_points/projector_points are ordered row-by-row
        # Find unique X and Y coordinates in projector space to define the grid
        # Actually, projector_points ARE a perfect grid by construction in generate_calibration_pattern
        self.unique_proj_x = np.unique(projector_points[:, 0])
        self.unique_proj_y = np.unique(projector_points[:, 1])

        self.rows = len(self.unique_proj_y)
        self.cols = len(self.unique_proj_x)

        # Map (px, py) to residual (dx, dy)
        self.grid_residuals = np.zeros((self.rows, self.cols, 2), dtype=np.float32)

        # Sort projector points to map them to the grid index
        # This is a bit robust against jumbled points if they ever occur
        for i in range(len(projector_points)):
            px, py = projector_points[i]
            ix = np.where(self.unique_proj_x == px)[0][0]
            iy = np.where(self.unique_proj_y == py)[0][0]
            self.grid_residuals[iy, ix] = self.residuals[i]

    def apply_correction(self, points_camera: np.ndarray) -> np.ndarray:
        """
        Applies homography followed by non-linear residual correction.
        points_camera: (N, 2) or (N, 1, 2)
        """
        if points_camera.size == 0:
            return points_camera

        points = points_camera.reshape(-1, 1, 2)
        # Linear transform
        pts_proj_raw = cv2.perspectiveTransform(points, self.homography).reshape(-1, 2)

        corrected_pts = []
        for p in pts_proj_raw:
            # Bilinear interpolation of residuals
            rx, ry = self._interpolate_residual(p[0], p[1])
            corrected_pts.append([p[0] + rx, p[1] + ry])

        return np.array(corrected_pts, dtype=np.float32).reshape(-1, 1, 2)

    def correct_theoretical_point(self, px: float, py: float) -> Tuple[float, float]:
        """
        Corrects a point that is already in theoretical projector space (e.g. from warped image).
        """
        rx, ry = self._interpolate_residual(px, py)
        return px + rx, py + ry

    def _interpolate_residual(self, px: float, py: float) -> Tuple[float, float]:
        """Performs bilinear interpolation of the residual at screen pixel (px, py)."""
        # 1. Find the cell in the projector grid
        # self.unique_proj_x/y are sorted
        ix_high = np.searchsorted(self.unique_proj_x, px)
        iy_high = np.searchsorted(self.unique_proj_y, py)

        # Handle out of bounds by clamping to edge residuals (Nearest Neighbor at edges)
        ix_high = max(1, min(ix_high, self.cols - 1))
        iy_high = max(1, min(iy_high, self.rows - 1))
        ix_low = ix_high - 1
        iy_low = iy_high - 1

        # Grid coordinates
        x0, x1 = self.unique_proj_x[ix_low], self.unique_proj_x[ix_high]
        y0, y1 = self.unique_proj_y[iy_low], self.unique_proj_y[iy_high]

        # Normalized coordinates [0, 1] within cell
        tx = (px - x0) / (x1 - x0) if x1 != x0 else 0
        ty = (py - y0) / (y1 - y0) if y1 != y0 else 0
        tx = max(0, min(1, tx))
        ty = max(0, min(1, ty))

        # Residuals at corners
        r00 = self.grid_residuals[iy_low, ix_low]
        r10 = self.grid_residuals[iy_low, ix_high]
        r01 = self.grid_residuals[iy_high, ix_low]
        r11 = self.grid_residuals[iy_high, ix_high]

        # Bilinear interpolation
        r = (
            r00 * (1 - tx) * (1 - ty)
            + r10 * tx * (1 - ty)
            + r01 * (1 - tx) * ty
            + r11 * tx * ty
        )

        return r[0], r[1]
