import numpy as np
import cv2
import logging
import os
from typing import Optional


class CameraProjectionModel:
    """
    Encapsulates camera intrinsics and extrinsics to perform 3D reconstructions
    from 2D camera images (parallax correction).
    """

    def __init__(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        rvec: np.ndarray,
        tvec: np.ndarray,
    ):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.rvec = rvec
        self.tvec = tvec

        self.R, _ = cv2.Rodrigues(self.rvec)
        self.RT = self.R.T
        # Camera center in world coordinates: C = -R^T * t
        self.camera_center = -(self.RT @ self.tvec.flatten())

    def reconstruct_world_points(
        self, pixel_pts: np.ndarray, height_mm: float = 0.0
    ) -> np.ndarray:
        """
        Intersects rays from the camera through pixel_pts with the plane Z = height_mm.
        Returns (N, 2) array of [X, Y] world coordinates.
        """
        if pixel_pts.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # 1. Undistort points and convert to normalized camera coordinates
        pts_reshaped = pixel_pts.reshape(-1, 1, 2).astype(np.float32)
        undistorted = cv2.undistortPoints(
            pts_reshaped, self.camera_matrix, self.dist_coeffs
        )
        xn = undistorted[:, 0, 0]
        yn = undistorted[:, 0, 1]

        # 2. Transform ray directions to world space
        # rays_cam = [xn, yn, 1]^T
        N = xn.shape[0]
        rays_cam = np.vstack([xn, yn, np.ones(N)])  # 3 x N
        rays_world = self.RT @ rays_cam  # 3 x N

        # 3. Intersect rays with plane Z = height_mm
        # P = C + s * v_world
        # P.z = C.z + s * v_world.z = height_mm  => s = (height_mm - C.z) / v_world.z
        cz = self.camera_center[2]
        vz = rays_world[2, :]

        # Avoid division by zero for rays parallel to the plane
        s = (height_mm - cz) / (vz + 1e-9)
        p_world = self.camera_center.reshape(3, 1) + s * rays_world  # 3 x N

        return p_world[:2, :].T.astype(np.float32)

    def project_world_to_camera(self, points_3d: np.ndarray) -> np.ndarray:
        """Standard projection of 3D world points to camera pixels."""
        if points_3d.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        pts_p, _ = cv2.projectPoints(
            points_3d.astype(np.float32),
            self.rvec,
            self.tvec,
            self.camera_matrix,
            self.dist_coeffs,
        )
        return pts_p.reshape(-1, 2).astype(np.float32)


class Projector3DModel:
    """
    Encapsulates the 3D projection model for the projector.
    Can fall back to 2D Homography if 3D calibration is missing or disabled.
    """

    def __init__(
        self,
        mtx: Optional[np.ndarray] = None,
        dist: Optional[np.ndarray] = None,
        rvec: Optional[np.ndarray] = None,
        tvec: Optional[np.ndarray] = None,
        homography: Optional[np.ndarray] = None,
        use_3d: bool = False,
    ):
        self.mtx = mtx
        self.dist = dist
        self.rvec = rvec
        self.tvec = tvec
        self.H = homography
        self.use_3d = use_3d

    def project_world_to_projector(self, points_3d: np.ndarray) -> np.ndarray:
        """
        Maps (N, 3) World points to (N, 2) Projector pixels.
        If use_projector_3d_model is False, falls back to 2D Homography (assuming Z=0).
        """
        if self.use_3d and self.mtx is not None and self.rvec is not None:
            # Full 3D Projective transformation
            pts_p, _ = cv2.projectPoints(
                points_3d.astype(np.float32),
                self.rvec,
                self.tvec,
                self.mtx,
                self.dist,
            )
            return pts_p.reshape(-1, 2)
        elif self.H is not None:
            # Fallback to 2D Homography (ignoring Z height)
            pts_2d = points_3d[:, :2].astype(np.float32).reshape(-1, 1, 2)
            pts_p = cv2.perspectiveTransform(pts_2d, self.H)
            return pts_p.reshape(-1, 2)
        else:
            logging.warning(
                "Projector3DModel: No calibration available for projection."
            )
            return points_3d[:, :2].astype(np.float32)

    @staticmethod
    def load_from_storage(storage, use_3d: bool = False) -> "Projector3DModel":
        """Loads 3D calibration and/or Homography from storage."""
        mtx = None
        dist = None
        rvec = None
        tvec = None
        H = None

        if storage is None:
            return Projector3DModel(use_3d=use_3d)

        # Try to load 3D calibration
        ext_path = storage.get_data_path("projector_3d_calibration.npz")
        if os.path.exists(ext_path):
            try:
                data = np.load(ext_path)
                mtx = data["mtx"]
                dist = data["dist"]
                rvec = data["rvec"]
                tvec = data["tvec"]
                logging.info(
                    "Projector3DModel: Loaded 3D calibration from %s", ext_path
                )
            except Exception as e:
                logging.error("Projector3DModel: Error loading 3D calibration: %s", e)

        # Try to load 2D Homography
        h_path = storage.get_data_path("projector_calibration.npz")
        if os.path.exists(h_path):
            try:
                data = np.load(h_path)
                H = data["projector_matrix"]
                logging.info("Projector3DModel: Loaded 2D Homography from %s", h_path)
            except Exception as e:
                logging.error("Projector3DModel: Error loading 2D Homography: %s", e)

        return Projector3DModel(
            mtx=mtx, dist=dist, rvec=rvec, tvec=tvec, homography=H, use_3d=use_3d
        )
