import logging
import os

import numpy as np


logger = logging.getLogger(__name__)


def resolve_lens_intrinsics(camera_side: str) -> tuple[np.ndarray, np.ndarray]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    left_file = os.path.join(base_dir, "camera_left_calibration.npz")
    right_file = os.path.join(base_dir, "camera_right_calibration.npz")
    default_file = os.path.join(base_dir, "camera_calibration.npz")

    target_file = left_file if camera_side == "left" else right_file

    if os.path.exists(target_file):
        data = np.load(target_file)
        logger.info(f"Loaded intrinsics for {camera_side} from {target_file}")
        return data["camera_matrix"], data["distortion_coefficients"]

    if os.path.exists(default_file):
        data = np.load(default_file)
        logger.info(f"Falling back to {default_file} for {camera_side}")
        return data["camera_matrix"], data["distortion_coefficients"]

    logger.error("Neither %s nor %s exists.", target_file, default_file)
    raise FileNotFoundError(
        f"Calibration file not found for {camera_side}. Expected {target_file} or {default_file}"
    )
