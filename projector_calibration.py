import sys
import os
import numpy as np

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.calibration_logic import run_calibration_sequence


def main():
    width = 1920
    height = 1080

    # Initialize Camera
    print("Initializing Camera...")
    with Camera() as cam:
        matrix = run_calibration_sequence(cam, width=width, height=height)

    if matrix is not None:
        print("Transformation matrix:")
        print(matrix)

        output_file = "projector_calibration.npz"
        print(f"Saving calibration to {output_file}...")
        np.savez(
            output_file, projector_matrix=matrix, resolution=np.array([width, height])
        )
        print("Saved successfully.")
    else:
        print("Calibration failed.")


if __name__ == "__main__":
    main()
