import numpy as np
import cv2


def reproduce():
    # Simulate camera extrinsics
    rvec_c = np.array([0, 0, 0], dtype=np.float32)
    tvec_c = np.array(
        [[10], [20], [30]], dtype=np.float32
    )  # (3, 1) as returned by some cv2 functions

    R_c, _ = cv2.Rodrigues(rvec_c)
    C_w = -R_c.T @ tvec_c  # (3, 3) @ (3, 1) -> (3, 1)

    print(f"C_w shape: {C_w.shape}")

    # Simulate ray vector
    v_w = np.array([0.1, 0.2, 0.3], dtype=np.float32)  # (3,)
    print(f"v_w shape: {v_w.shape}")

    t = 100.0
    P_world = C_w + t * v_w
    print(f"P_world shape: {P_world.shape}")
    print(f"P_world content:\n{P_world}")

    # Now simulate the calibration preparation
    correspondences = [(P_world, np.array([100, 200], dtype=np.float32))]

    # This is what's in calibrate_projector_3d
    obj_points = [
        np.ascontiguousarray([c[0] for c in correspondences], dtype=np.float32).reshape(
            -1, 1, 3
        )
    ]
    img_points = [
        np.ascontiguousarray([c[1] for c in correspondences], dtype=np.float32).reshape(
            -1, 1, 2
        )
    ]

    print(f"Obj Points shape: {obj_points[0].shape}")
    print(f"Img Points shape: {img_points[0].shape}")

    if obj_points[0].shape[0] != img_points[0].shape[0]:
        print("MISMATCH DETECTED!")
        print(
            f"Expected {img_points[0].shape[0]} object points, but got {obj_points[0].shape[0]}"
        )


if __name__ == "__main__":
    reproduce()
