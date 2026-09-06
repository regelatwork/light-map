"""
Module for loading camera lens intrinsics with fallback resolution.
"""

from pathlib import Path

import numpy as np


def load_intrinsics(camera_side: str, base_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Loads camera intrinsics (K, dist) from .npz files.

    Args:
        camera_side: "left" or "right"
        base_path: The directory where calibration files are stored.

    Returns:
        A tuple (K, dist) where K is a 3x3 numpy array and dist is a 5-element numpy array.
    """
    if camera_side == "left":
        files = [base_path / "camera_left_calibration.npz", base_path / "camera_calibration.npz"]
    else:
        files = [base_path / "camera_right_calibration.npz", base_path / "camera_calibration.npz"]

    for file_path in files:
        if file_path.exists():
            data = np.load(file_path, allow_pickle=True)
            K = np.array(data["K"])
            dist = np.array(data["dist"])
            return K, dist

    # Fallback to default calibration if no file is found
    # Default: 640x480 resolution with 500mm focal length
    K_default = np.array(
        [[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    dist_default = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    return K_default, dist_default
