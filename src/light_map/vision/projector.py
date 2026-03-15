import numpy as np
import cv2
import logging
import os
from typing import Optional


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
            # cv2.projectPoints expects (N, 3) or (N, 1, 3)
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
            # cv2.perspectiveTransform expects (N, 1, 2)
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
        """
        Loads 3D calibration and/or Homography from storage.
        """
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
