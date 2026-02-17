import sys
import os
import numpy as np

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.calibration_logic import run_calibration_sequence
from light_map.display_utils import get_screen_resolution


def main():
    proj_width, proj_height = get_screen_resolution()
    print(f"Detected Screen Resolution: {proj_width}x{proj_height}")

    # Initialize Camera
    print("Initializing Camera...")
    with Camera() as cam:
        result = run_calibration_sequence(
            cam, projector_width=proj_width, projector_height=proj_height
        )

    if result is not None:
        matrix, cam_pts, proj_pts = result
        print("Transformation matrix:")
        print(matrix)

        output_file = "projector_calibration.npz"
        print(f"Saving calibration to {output_file}...")
        np.savez(
            output_file,
            projector_matrix=matrix,
            camera_points=cam_pts,
            projector_points=proj_pts,
            resolution=np.array([cam.width, cam.height]),
            camera_resolution=np.array([cam.width, cam.height]),
            projector_resolution=np.array([proj_width, proj_height]),
        )
        print("Saved successfully.")
    else:
        print("Calibration failed.")


if __name__ == "__main__":
    main()
