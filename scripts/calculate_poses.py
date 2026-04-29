import json
from pathlib import Path

import cv2
import numpy as np


def get_position(rotation_vector, translation_vector):
    """Calculates the 3D position [X, Y, Z] from rotation and translation vectors."""
    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    # Position in world coordinates: C = -R^T * t
    world_position = -rotation_matrix.T @ translation_vector
    return world_position.flatten()


def main():
    home = Path.home()
    data_dir = home / ".local" / "share" / "light_map"
    config_dir = home / ".config" / "light_map"
    config_file = config_dir / "map_state.json"

    # Files
    camera_extrinsics_file = data_dir / "camera_extrinsics.npz"
    projector_3d_file = data_dir / "projector_3d_calibration.npz"

    # Load Overrides from Config
    overrides = {"x": None, "y": None, "z": None}
    if config_file.exists():
        try:
            with open(config_file) as f:
                config_data = json.load(f)
                global_settings = config_data.get("global", {})
                overrides["x"] = global_settings.get("projector_pos_x_override")
                overrides["y"] = global_settings.get("projector_pos_y_override")
                overrides["z"] = global_settings.get("projector_pos_z_override")
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")

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

        # Apply Overrides
        adj_x = overrides["x"] if overrides["x"] is not None else world_position[0]
        adj_y = overrides["y"] if overrides["y"] is not None else world_position[1]
        adj_z = overrides["z"] if overrides["z"] is not None else world_position[2]
        has_overrides = any(v is not None for v in overrides.values())

        print("PROJECTOR POSITION (World mm):")
        if has_overrides:
            print(f"  X: {adj_x:8.2f} mm (Calibrated: {world_position[0]:.2f})")
            print(f"  Y: {adj_y:8.2f} mm (Calibrated: {world_position[1]:.2f})")
            print(f"  Z: {adj_z:8.2f} mm (Calibrated: {world_position[2]:.2f})")
            print("  NOTE: Using manual position overrides.")
        else:
            print(f"  X: {world_position[0]:8.2f} mm")
            print(f"  Y: {world_position[1]:8.2f} mm")
            print(f"  Z: {world_position[2]:8.2f} mm (Height above table)")

        print(f"  RMS Error: {rms_error:.3f} px")
    else:
        print(f"Projector 3D calibration file not found at: {projector_3d_file}")

    print("-" * 40)


if __name__ == "__main__":
    main()
