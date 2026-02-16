import cv2
import numpy as np
import glob
import os


CHECKERBOARD_DIMS = (6, 9)  # Standard chessboard dimensions
CALIBRATION_FILE = "camera_calibration.npz"


def load_calibration_images(image_dir, extensions=("jpg", "jpeg")):
    """Loads image paths from a directory matching specific extensions."""
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(image_dir, f"*.{ext}")))
    return sorted(images)


def find_corners(image, checkerboard_dims, criteria):
    """
    Finds and refines checkerboard corners in a single image.

    Returns:
        ret (bool): Whether corners were found.
        corners2: Refined corner coordinates.
        image: Image with corners drawn (if found).
        gray: Grayscale version of the image (used for calibration shape).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    flags = (
        cv2.CALIB_CB_ADAPTIVE_THRESH
        + cv2.CALIB_CB_FAST_CHECK
        + cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    ret, corners = cv2.findChessboardCorners(gray, checkerboard_dims, flags)

    corners2 = None
    if ret:
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        # Draw corners for visualization (optional, usually done by caller)
        # image = cv2.drawChessboardCorners(image, checkerboard_dims, corners2, ret)

    return ret, corners2, gray


def process_chessboard_images(
    images: list[np.ndarray], checkerboard_dims: tuple[int, int] = CHECKERBOARD_DIMS
) -> tuple[tuple[np.ndarray, np.ndarray], list[np.ndarray]] | None:
    """
    Processes a list of chessboard images to perform camera calibration.

    Args:
        images: List of numpy arrays, each representing a chessboard image.
        checkerboard_dims: Dimensions of the inner corners of the checkerboard (cols, rows).

    Returns:
        A tuple containing:
            - (camera_matrix, dist_coeffs) if calibration is successful.
            - list of rotation and translation vectors (rvecs, tvecs)
        Returns None if calibration fails.
    """
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objp = np.zeros((1, checkerboard_dims[0] * checkerboard_dims[1], 3), np.float32)
    objp[0, :, :2] = np.mgrid[
        0 : checkerboard_dims[0], 0 : checkerboard_dims[1]
    ].T.reshape(-1, 2)

    objpoints = []  # 3d point in real world space
    imgpoints = []  # 2d points in image plane.

    image_shape = None

    for img in images:
        ret, corners2, gray = find_corners(img, checkerboard_dims, criteria)

        if ret:
            objpoints.append(objp)
            imgpoints.append(corners2)
            if image_shape is None:
                image_shape = gray.shape[::-1]

    if not objpoints or image_shape is None:
        print("Error: No chessboard corners found in any images for calibration.")
        return None

    try:
        ret, matrix, distortion, r_vecs, t_vecs = cv2.calibrateCamera(
            objpoints, imgpoints, image_shape, None, None
        )
        if ret:
            return (matrix, distortion), (r_vecs, t_vecs)
    except cv2.error as e:
        print(f"OpenCV calibration error: {e}")

    return None


def save_camera_calibration(camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
    """Saves the camera matrix and distortion coefficients to a file."""
    np.savez(CALIBRATION_FILE, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)
    print(f"Camera calibration saved to {CALIBRATION_FILE}")


def calibrate_camera_from_images(image_paths, checkerboard_dims=(6, 9)):
    """
    Performs camera calibration using a list of image paths.
    """
    # Termination criteria for corner refinement
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # 3D points in real world space
    objp = np.zeros((1, checkerboard_dims[0] * checkerboard_dims[1], 3), np.float32)
    objp[0, :, :2] = np.mgrid[
        0 : checkerboard_dims[0], 0 : checkerboard_dims[1]
    ].T.reshape(-1, 2)

    objpoints = []  # 3d point in real world space
    imgpoints = []  # 2d points in image plane.

    image_shape = None

    for fname in image_paths:
        img = cv2.imread(fname)
        if img is None:
            print(f"Warning: Could not read image {fname}")
            continue

        ret, corners2, gray = find_corners(img, checkerboard_dims, criteria)

        if ret:
            objpoints.append(objp)
            imgpoints.append(corners2)
            if image_shape is None:
                image_shape = gray.shape[::-1]

    if not objpoints:
        raise RuntimeError("No chessboard corners found in any images.")

    ret, matrix, distortion, r_vecs, t_vecs = cv2.calibrateCamera(
        objpoints, imgpoints, image_shape, None, None
    )

    return matrix, distortion
