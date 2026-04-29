import os
import sys


# Ensure we can import the local package
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import argparse
import logging

from light_map.calibration.calibration import (
    calibrate_camera_from_images,
    load_calibration_images,
    save_camera_calibration,
)
from light_map.core.display_utils import setup_logging
from light_map.core.storage import StorageManager


def run_calibrate(args):
    storage = StorageManager(base_dir=args.base_dir)
    storage.ensure_dirs()

    setup_logging()
    logger = logging.getLogger(__name__)
    image_dir = args.image_dir
    logger.info("Looking for images in %s...", image_dir)

    images = load_calibration_images(image_dir)

    if not images:
        logger.error(
            "No images found. Please ensure .jpg or .jpeg files are in the 'images' directory."
        )
        return

    logger.info("Found %d images. Starting calibration...", len(images))

    try:
        camera_matrix, distortion_coefficients = calibrate_camera_from_images(images)

        logger.info("Camera matrix:\n%s", camera_matrix)
        logger.info("Distortion coefficients:\n%s", distortion_coefficients)

        output_file = storage.get_data_path("camera_calibration.npz")
        save_camera_calibration(
            camera_matrix, distortion_coefficients, output_file=output_file
        )
        logger.info("Calibration saved to %s", output_file)

    except RuntimeError as e:
        logger.error("Calibration failed: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera Intrinsics Calibration")
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Override base directory for config and data",
        default=None,
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        help="Directory containing calibration images",
        default="./images",
    )
    args = parser.parse_args()
    run_calibrate(args)
