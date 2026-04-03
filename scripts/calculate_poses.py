import numpy as np
import cv2
from pathlib import Path


def get_position(rotation_vector, translation_vector):
    """Calculates the 3D position [X, Y, Z] from rotation and translation vectors."""
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    # Position in world coordinates: C = -R^T * t
    world_position = -rotation_matrix.T @ translation_vector
    return world_position.flatten()


def main():
    home = Path.home()
    data_dir = home / ".local" / "share" / "light_map"
    # config_dir = home / ".config" / "light_map"

    # Files
    camera_extrinsics_file = data_dir / "camera_extrinsics.npz"
    projector_3d_file = data_dir / "projector_3d_calibration.npz"

    print("-" * 40)
    print("LIGHT MAP: 3D POSE CALCULATION")
    print("-" * 40)

    # 1. Camera Pose
    if camera_extrinsics_file.exists():
        data = np.load(camera_extrinsics_file)
        rotation_vector = data["rotation_vector"]
        translation_vector = data["translation_vector"]
        world_position = get_position(rotation_vector, translation_vector)
        print("CAMERA POSITION (World mm):")
        print(f"  X: {world_position[0]:8.2f} mm")
        print(f"  Y: {world_position[1]:8.2f} mm")
        print(f"  Z: {world_position[2]:8.2f} mm (Height above table)")
    else:
        print(f"Camera extrinsics file not found at: {camera_extrinsics_file}")

    print("-" * 40)

    # 2. Projector Pose
    if projector_3d_file.exists():
        data = np.load(projector_3d_file)
        rotation_vector = data["rotation_vector"]
        translation_vector = data["translation_vector"]
        rms_error = data.get("rms", 0.0)
        world_position = get_position(rotation_vector, translation_vector)
        print("PROJECTOR POSITION (World mm):")
        print(f"  X: {world_position[0]:8.2f} mm")
        print(f"  Y: {world_position[1]:8.2f} mm")
        print(f"  Z: {world_position[2]:8.2f} mm (Height above table)")
        print(f"  RMS Error: {rms_error:.3f} px")
    else:
        print(f"Projector 3D calibration file not found at: {projector_3d_file}")

    print("-" * 40)


if __name__ == "__main__":
    main()
