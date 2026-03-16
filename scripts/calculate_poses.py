import numpy as np
import cv2
from pathlib import Path


def get_position(rvec, tvec):
    """Calculates the 3D position [X, Y, Z] from rotation and translation vectors."""
    R, _ = cv2.Rodrigues(rvec)
    # Position in world coordinates: C = -R^T * t
    pos = -R.T @ tvec
    return pos.flatten()


def main():
    home = Path.home()
    data_dir = home / ".local" / "share" / "light_map"
    config_dir = home / ".config" / "light_map"

    # Files
    cam_ext_file = data_dir / "camera_extrinsics.npz"
    proj_3d_file = config_dir / "projector_3d_calibration.npz"

    print("-" * 40)
    print("LIGHT MAP: 3D POSE CALCULATION")
    print("-" * 40)

    # 1. Camera Pose
    if cam_ext_file.exists():
        data = np.load(cam_ext_file)
        rvec = data["rvec"]
        tvec = data["tvec"]
        pos = get_position(rvec, tvec)
        print("CAMERA POSITION (World mm):")
        print(f"  X: {pos[0]:8.2f} mm")
        print(f"  Y: {pos[1]:8.2f} mm")
        print(f"  Z: {pos[2]:8.2f} mm (Height above table)")
    else:
        print(f"Camera extrinsics file not found at: {cam_ext_file}")

    print("-" * 40)

    # 2. Projector Pose
    if proj_3d_file.exists():
        data = np.load(proj_3d_file)
        rvec = data["rvec"]
        tvec = data["tvec"]
        rms = data.get("rms", 0.0)
        pos = get_position(rvec, tvec)
        print("PROJECTOR POSITION (World mm):")
        print(f"  X: {pos[0]:8.2f} mm")
        print(f"  Y: {pos[1]:8.2f} mm")
        print(f"  Z: {pos[2]:8.2f} mm (Height above table)")
        print(f"  RMS Error: {rms:.3f} px")
    else:
        print(f"Projector 3D calibration file not found at: {proj_3d_file}")

    print("-" * 40)


if __name__ == "__main__":
    main()
