import cv2
import numpy as np
import glob
import os
import logging
from light_map.core.constants import DEFAULT_CHECKERBOARD_DIMS


CHECKERBOARD_DIMS = DEFAULT_CHECKERBOARD_DIMS  # Standard chessboard dimensions
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
        refined_corners: Refined corner coordinates.
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

    refined_corners = None
    if ret:
        refined_corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        # Draw corners for visualization (optional, usually done by caller)
        # image = cv2.drawChessboardCorners(image, checkerboard_dims, refined_corners, ret)

    return ret, refined_corners, gray


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
            - (camera_matrix, distortion_coefficients) if calibration is successful.
            - list of rotation and translation vectors (rotation_vectors, translation_vectors)
        Returns None if calibration fails.
    """
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    object_point_template = np.zeros(
        (1, checkerboard_dims[0] * checkerboard_dims[1], 3), np.float32
    )
    object_point_template[0, :, :2] = np.mgrid[
        0 : checkerboard_dims[0], 0 : checkerboard_dims[1]
    ].T.reshape(-1, 2)

    object_points = []  # 3d point in real world space
    image_points = []  # 2d points in image plane.

    image_shape = None

    for img in images:
        ret, refined_corners, gray = find_corners(img, checkerboard_dims, criteria)

        if ret:
            object_points.append(object_point_template)
            image_points.append(refined_corners)
            if image_shape is None:
                image_shape = gray.shape[::-1]

    if not object_points or image_shape is None:
        logging.error("No chessboard corners found in any images for calibration.")
        return None

    try:
        (
            ret,
            camera_matrix,
            distortion_coefficients,
            rotation_vectors,
            translation_vectors,
        ) = cv2.calibrateCamera(object_points, image_points, image_shape, None, None)
        if ret:
            return (camera_matrix, distortion_coefficients), (
                rotation_vectors,
                translation_vectors,
            )
    except cv2.error as e:
        logging.error("OpenCV calibration error: %s", e)

    return None


def save_camera_calibration(
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
    output_file: str = CALIBRATION_FILE,
):
    """Saves the camera matrix and distortion coefficients to a file."""
    np.savez(
        output_file,
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
    )
    logging.info("Camera calibration saved to %s", output_file)


def save_camera_extrinsics(
    rotation_vector: np.ndarray,
    translation_vector: np.ndarray,
    output_file: str = "camera_extrinsics.npz",
):
    """Saves the camera extrinsic parameters (R, t) to a file."""
    np.savez(
        output_file,
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
    )
    logging.info("Camera extrinsics saved to %s", output_file)


def calibrate_camera_from_images(
    image_paths, checkerboard_dims=DEFAULT_CHECKERBOARD_DIMS
):
    """
    Performs camera calibration using a list of image paths.
    """
    # Termination criteria for corner refinement
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # 3D points in real world space
    object_point_template = np.zeros(
        (1, checkerboard_dims[0] * checkerboard_dims[1], 3), np.float32
    )
    object_point_template[0, :, :2] = np.mgrid[
        0 : checkerboard_dims[0], 0 : checkerboard_dims[1]
    ].T.reshape(-1, 2)

    object_points = []  # 3d point in real world space
    image_points = []  # 2d points in image plane.

    image_shape = None

    for fname in image_paths:
        img = cv2.imread(fname)
        if img is None:
            logging.warning("Could not read image %s", fname)
            continue

        ret, refined_corners, gray = find_corners(img, checkerboard_dims, criteria)

        if ret:
            object_points.append(object_point_template)
            image_points.append(refined_corners)
            if image_shape is None:
                image_shape = gray.shape[::-1]

    if not object_points:
        raise RuntimeError("No chessboard corners found in any images.")

    (
        ret,
        camera_matrix,
        distortion_coefficients,
        rotation_vectors,
        translation_vectors,
    ) = cv2.calibrateCamera(object_points, image_points, image_shape, None, None)

    return camera_matrix, distortion_coefficients
