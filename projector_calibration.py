import sys
import os
import numpy as np
import logging

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.calibration_logic import run_calibration_sequence
from light_map.display_utils import get_screen_resolution, setup_logging


def main():
    setup_logging(log_file="projector_calibration.log")
    proj_width, proj_height = get_screen_resolution()
    logging.info("Detected Screen Resolution: %dx%d", proj_width, proj_height)

    # Initialize Camera
    logging.info("Initializing Camera...")
    with Camera() as cam:
        result = run_calibration_sequence(
            cam, projector_width=proj_width, projector_height=proj_height
        )

    if result is not None:
        matrix, cam_pts, proj_pts = result
        logging.info("Transformation matrix:\n%s", matrix)

        output_file = "projector_calibration.npz"
        logging.info("Saving calibration to %s...", output_file)
        np.savez(
            output_file,
            projector_matrix=matrix,
            camera_points=cam_pts,
            projector_points=proj_pts,
            resolution=np.array([cam.width, cam.height]),
            camera_resolution=np.array([cam.width, cam.height]),
            projector_resolution=np.array([proj_width, proj_height]),
        )
        logging.info("Saved successfully.")
    else:
        logging.error("Calibration failed.")


if __name__ == "__main__":
    main()
