import sys
import os

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

import logging
from light_map.calibration import load_calibration_images, calibrate_camera_from_images
from light_map.display_utils import setup_logging
import numpy as np


def main():
    setup_logging(log_file="camera_calibration.log")
    image_dir = "./images"
    logging.info("Looking for images in %s...", image_dir)

    images = load_calibration_images(image_dir)

    if not images:
        logging.error(
            "No images found. Please ensure .jpg or .jpeg files are in the 'images' directory."
        )
        return

    logging.info("Found %d images. Starting calibration...", len(images))

    try:
        matrix, distortion = calibrate_camera_from_images(images)

        logging.info("Camera matrix:\n%s", matrix)
        logging.info("Distortion coefficients:\n%s", distortion)

        output_file = "camera_calibration.npz"
        np.savez(output_file, camera_matrix=matrix, dist_coeffs=distortion)
        logging.info("Calibration saved to %s", output_file)

    except RuntimeError as e:
        logging.error("Calibration failed: %s", e)


if __name__ == "__main__":
    main()
