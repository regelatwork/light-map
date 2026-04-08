import sys
import os
import numpy as np
import logging
import argparse

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
)
from light_map.core.storage import StorageManager
from light_map.map_config import MapConfigManager


def run_projector_calibrate(args):
    storage = StorageManager(base_dir=args.base_dir)
    storage.ensure_dirs()

    setup_logging()
    logger = logging.getLogger(__name__)

    projector_width, projector_height = get_screen_resolution()
    logger.info("Detected Screen Resolution: %dx%d", projector_width, projector_height)

    map_config = MapConfigManager(storage=storage)

    # State variables
    projector_matrix = None
    ppi = map_config.get_ppi()
    ground_points_camera = None
    ground_points_projector = None

    # Try to load existing projector calibration if needed
    calibration_file = storage.get_data_path("projector_calibration.npz")
    if os.path.exists(calibration_file):
        try:
            data = np.load(calibration_file)
            projector_matrix = data["projector_matrix"]
            ground_points_camera = data.get("camera_points")
            ground_points_projector = data.get("projector_points")
            logger.info("Loaded existing projector calibration.")
        except Exception as e:
            logger.warning("Failed to load existing projector calibration: %s", e)

    # Initialize Camera
    logger.info("Initializing Camera...")
    with Camera() as camera:
        for step in args.steps:
            if step == "projector":
                logger.info("--- Step 1: Projector Calibration (Homography) ---")
                result = run_calibration_sequence(
                    camera,
                    projector_width=projector_width,
                    projector_height=projector_height,
                )

                if result is not None:
                    projector_matrix, ground_points_camera, ground_points_projector = (
                        result
                    )
                    logger.info("Saving projector calibration...")
                    np.savez(
                        calibration_file,
                        projector_matrix=projector_matrix,
                        camera_points=ground_points_camera,
                        projector_points=ground_points_projector,
                        resolution=np.array([camera.width, camera.height]),
                        camera_resolution=np.array([camera.width, camera.height]),
                        projector_resolution=np.array(
                            [projector_width, projector_height]
                        ),
                    )
                    logger.info("Projector calibration saved to %s", calibration_file)
                else:
                    logger.error("Projector calibration failed!")
                    return

            elif step == "ppi":
                logger.info("--- Step 2: PPI Calibration ---")
                if projector_matrix is None:
                    logger.error("Cannot run PPI calibration without projector matrix!")
                    continue

                frame = camera.read()
                if frame is None:
                    logger.error("Failed to capture frame for PPI calibration.")
                    continue

                new_ppi = calculate_ppi_from_frame(
                    frame,
                    projector_matrix,
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
                    camera_matrix = data["camera_matrix"]
                    distortion_coefficients = data["distortion_coefficients"]

                # Use ground points from step 1
                if ground_points_camera is None or ground_points_projector is None:
                    logger.error("Ground points missing! Run 'projector' step first.")
                    continue

                frame = camera.read()
                if frame is None:
                    logger.error("Failed to capture frame for extrinsics calibration.")
                    continue

                # Prepare token heights (empty dict for base calibration)
                token_heights = {}
                token_sizes = {}

                ext_result = calibrate_extrinsics(
                    frame,
                    projector_matrix,
                    camera_matrix,
                    distortion_coefficients,
                    token_heights,
                    ppi,
                    ground_points_camera=ground_points_camera,
                    ground_points_projector=ground_points_projector,
                    token_sizes=token_sizes,
                )

                if ext_result is not None:
                    rotation_vector, translation_vector, _, _ = ext_result
                    extrinsics_file = storage.get_data_path("camera_extrinsics.npz")
                    np.savez(
                        extrinsics_file,
                        rotation_vector=rotation_vector,
                        translation_vector=translation_vector,
                    )
                    logger.info("Extrinsics saved to %s", extrinsics_file)
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
