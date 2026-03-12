import sys
import os
import numpy as np
import logging
import argparse
import cv2
import time
import math

# Ensure we can import the local package
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from light_map.camera import Camera
from light_map.calibration_logic import (
    run_calibration_sequence,
    calculate_ppi_from_frame,
    calibrate_extrinsics,
)
from light_map.display_utils import (
    get_screen_resolution,
    setup_logging,
    ProjectorWindow,
    draw_text_with_background,
)
from light_map.core.storage import StorageManager
from light_map.map_config import MapConfigManager


def run_projector_calibrate(args):
    storage = StorageManager(base_dir=args.base_dir)
    storage.ensure_dirs()

    setup_logging()
    logger = logging.getLogger(__name__)

    proj_width, proj_height = get_screen_resolution()
    logger.info("Detected Screen Resolution: %dx%d", proj_width, proj_height)

    map_config = MapConfigManager(storage=storage)

    # State variables
    projector_matrix = None
    ppi = map_config.get_ppi()
    ground_points_cam = None
    ground_points_proj = None

    # Try to load existing projector calibration if needed
    calib_file = storage.get_data_path("projector_calibration.npz")
    if os.path.exists(calib_file):
        try:
            data = np.load(calib_file)
            projector_matrix = data["projector_matrix"]
            ground_points_cam = data.get("camera_points")
            ground_points_proj = data.get("projector_points")
            logger.info("Loaded existing projector calibration.")
        except Exception as e:
            logger.warning("Failed to load existing projector calibration: %s", e)

    # Initialize Camera
    logger.info("Initializing Camera...")
    with Camera() as cam:
        for step in args.steps:
            if step == "projector":
                logger.info("--- Step 1: Projector Calibration (Homography) ---")
                result = run_calibration_sequence(
                    cam, projector_width=proj_width, projector_height=proj_height
                )

                if result is not None:
                    projector_matrix, ground_points_cam, ground_points_proj = result
                    logger.info("Saving projector calibration...")
                    np.savez(
                        calib_file,
                        projector_matrix=projector_matrix,
                        camera_points=ground_points_cam,
                        projector_points=ground_points_proj,
                        resolution=np.array([cam.width, cam.height]),
                        camera_resolution=np.array([cam.width, cam.height]),
                        projector_resolution=np.array([proj_width, proj_height]),
                    )
                    logger.info("Projector calibration saved to %s", calib_file)
                else:
                    logger.error("Projector calibration failed!")
                    return

            elif step == "ppi":
                logger.info("--- Step 2: PPI Calibration ---")
                if projector_matrix is None:
                    logger.error("Cannot run PPI calibration without projector matrix!")
                    continue

                new_ppi = calculate_ppi_from_frame(
                    cam,
                    projector_matrix,
                    proj_width,
                    proj_height,
                    current_ppi=ppi,
                )
                if new_ppi:
                    ppi = new_ppi
                    map_config.data.global_settings.projector_ppi = ppi
                    map_config.save()
                    logger.info("PPI updated to %.2f and saved.", ppi)
                else:
                    logger.warning("PPI calibration failed or cancelled.")

            elif step == "extrinsics":
                logger.info("--- Step 3: Extrinsics (Camera-to-World) ---")
                if projector_matrix is None:
                    logger.error(
                        "Cannot run extrinsics calibration without projector matrix!"
                    )
                    continue

                # We need intrinsics to do extrinsics
                intrinsics_file = storage.get_data_path("camera_calibration.npz")
                if not os.path.exists(intrinsics_file):
                    logger.error(
                        "Camera intrinsics missing! Run 'light-map calibrate' first."
                    )
                    continue

                with np.load(intrinsics_file) as data:
                    mtx = data["mtx"]
                    dist = data["dist"]

                # Use ground points from step 1
                if ground_points_cam is None or ground_points_proj is None:
                    logger.error(
                        "Ground points missing! Run 'projector' step first."
                    )
                    continue

                ext_result = calibrate_extrinsics(
                    cam,
                    mtx,
                    dist,
                    projector_matrix,
                    ground_points_cam,
                    ground_points_proj,
                    proj_width,
                    proj_height,
                )

                if ext_result is not None:
                    rvec, tvec = ext_result
                    ext_file = storage.get_data_path("camera_extrinsics.npz")
                    np.savez(ext_file, rvec=rvec, tvec=tvec)
                    logger.info("Extrinsics saved to %s", ext_file)
                else:
                    logger.error("Extrinsics calibration failed!")

    logger.info("All selected calibration steps finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Projector and Camera Calibration")
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Override base directory for config and data",
        default=None,
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["projector", "ppi", "extrinsics"],
        default=["projector", "ppi", "extrinsics"],
        help="Calibration steps to run (default: all)",
    )
    args = parser.parse_args()
    run_projector_calibrate(args)
