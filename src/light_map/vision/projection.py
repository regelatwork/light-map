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
        distortion_coefficients: np.ndarray,
        rotation_vector: np.ndarray,
        translation_vector: np.ndarray,
    ):
        self.camera_matrix = camera_matrix
        self.distortion_coefficients = distortion_coefficients
        self.rotation_vector = rotation_vector
        self.translation_vector = translation_vector

        self.rotation_matrix, _ = cv2.Rodrigues(self.rotation_vector)
        self.rotation_matrix_inv = self.rotation_matrix.T
        # Camera center in world coordinates: C = -R^T * t
        self.camera_center = -(
            self.rotation_matrix_inv @ self.translation_vector.flatten()
        )

    def reconstruct_world_points(
        self, pixel_points: np.ndarray, height_mm: float = 0.0
    ) -> np.ndarray:
        """
        Intersects rays from the camera through pixel_points with the plane Z = height_mm.
        Returns (N, 2) array of [X, Y] world coordinates.
        """
        if pixel_points.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # 1. Undistort points and convert to normalized camera coordinates
        pixels_reshaped = pixel_points.reshape(-1, 1, 2).astype(np.float32)
        undistorted = cv2.undistortPoints(
            pixels_reshaped, self.camera_matrix, self.distortion_coefficients
        )
        x_normalized = undistorted[:, 0, 0]
        y_normalized = undistorted[:, 0, 1]

        # 2. Transform ray directions to world space
        N = x_normalized.shape[0]
        camera_rays = np.vstack([x_normalized, y_normalized, np.ones(N)])  # 3 x N
        world_rays = self.rotation_matrix_inv @ camera_rays  # 3 x N

        # 3. Intersect rays with plane Z = height_mm
        # P = C + s * v_world
        # P.z = C.z + s * v_world.z = height_mm  => s = (height_mm - C.z) / v_world.z
        camera_center_z = self.camera_center[2]
        world_rays_z = world_rays[2, :]

        # Avoid division by zero for rays parallel to the plane
        ray_distance = (height_mm - camera_center_z) / (world_rays_z + 1e-9)
        world_points_3d = (
            self.camera_center.reshape(3, 1) + ray_distance * world_rays
        )  # 3 x N

        return world_points_3d[:2, :].T.astype(np.float32)

    def project_world_to_camera(self, world_points: np.ndarray) -> np.ndarray:
        """Standard projection of 3D world points to camera pixels."""
        if world_points.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        projected_pixels, _ = cv2.projectPoints(
            world_points.astype(np.float32),
            self.rotation_vector,
            self.translation_vector,
            self.camera_matrix,
            self.distortion_coefficients,
        )
        return projected_pixels.reshape(-1, 2).astype(np.float32)


class Projector3DModel:
    """
    Encapsulates the 3D projection model for the projector.
    Can fall back to 2D Homography if 3D calibration is missing or disabled.
    """

    def __init__(
        self,
        intrinsic_matrix: Optional[np.ndarray] = None,
        distortion_coefficients: Optional[np.ndarray] = None,
        rotation_vector: Optional[np.ndarray] = None,
        translation_vector: Optional[np.ndarray] = None,
        homography_matrix: Optional[np.ndarray] = None,
        use_3d: bool = False,
    ):
        self.intrinsic_matrix = intrinsic_matrix
        self.distortion_coefficients = distortion_coefficients
        self.rotation_vector = rotation_vector
        self.translation_vector = translation_vector
        self.homography_matrix = homography_matrix
        self.use_3d = use_3d

    @property
    def is_calibrated_3d(self) -> bool:
        """Returns True if full 3D calibration data is present."""
        return self.intrinsic_matrix is not None and self.rotation_vector is not None

    def project_world_to_projector(self, world_points: np.ndarray) -> np.ndarray:
        """
        Maps (N, 3) World points to (N, 2) Projector pixels.
        If use_projector_3d_model is False, falls back to 2D Homography (assuming Z=0).
        """
        if (
            self.use_3d
            and self.intrinsic_matrix is not None
            and self.rotation_vector is not None
        ):
            # Full 3D Projective transformation
            projector_pixels, _ = cv2.projectPoints(
                world_points.astype(np.float32),
                self.rotation_vector,
                self.translation_vector,
                self.intrinsic_matrix,
                self.distortion_coefficients,
            )
            return projector_pixels.reshape(-1, 2)
        elif self.homography_matrix is not None:
            # Fallback to 2D Homography (ignoring Z height)
            # NOTE: This assumes homography_matrix is a World-to-Projector mapping.
            # If it's a Camera-to-Projector mapping (common in this project), this will be incorrect.
            points_2d = world_points[:, :2].astype(np.float32).reshape(-1, 1, 2)
            projected_pixels = cv2.perspectiveTransform(
                points_2d, self.homography_matrix
            )
            return projected_pixels.reshape(-1, 2)
        else:
            logging.warning(
                "Projector3DModel: No calibration available for projection."
            )
            return world_points[:, :2].astype(np.float32)

    @staticmethod
    def load_from_storage(storage, use_3d: bool = False) -> "Projector3DModel":
        """Loads 3D calibration and/or Homography from storage."""
        intrinsic_matrix = None
        distortion_coefficients = None
        rotation_vector = None
        translation_vector = None
        homography_matrix = None

        if storage is None:
            return Projector3DModel(use_3d=use_3d)

        # Try to load 3D calibration
        ext_path = storage.get_data_path("projector_3d_calibration.npz")
        if os.path.exists(ext_path):
            try:
                with np.load(ext_path) as data:
                    intrinsic_matrix = data.get("intrinsic_matrix")
                    if intrinsic_matrix is None:
                        intrinsic_matrix = data.get("mtx")
                    distortion_coefficients = data.get("distortion_coefficients")
                    if distortion_coefficients is None:
                        distortion_coefficients = data.get("dist")
                    rotation_vector = data.get("rotation_vector")
                    if rotation_vector is None:
                        rotation_vector = data.get("rvec")
                    translation_vector = data.get("translation_vector")
                    if translation_vector is None:
                        translation_vector = data.get("tvec")
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
                homography_matrix = data["projector_matrix"]
                logging.info("Projector3DModel: Loaded 2D Homography from %s", h_path)
            except Exception as e:
                logging.error("Projector3DModel: Error loading 2D Homography: %s", e)

        return Projector3DModel(
            intrinsic_matrix=intrinsic_matrix,
            distortion_coefficients=distortion_coefficients,
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
            homography_matrix=homography_matrix,
            use_3d=use_3d,
        )


class ProjectionService:
    """
    High-level service that coordinates CameraProjectionModel and Projector3DModel
    to provide end-to-end mapping (e.g., Camera Pixels -> Projector Pixels).
    """

    def __init__(
        self, camera_model: CameraProjectionModel, projector_model: Projector3DModel
    ):
        self.camera_model = camera_model
        self.projector_model = projector_model

    def project_camera_to_projector(
        self, camera_pixels: np.ndarray, height_mm: float = 0.0
    ) -> np.ndarray:
        """
        Maps camera pixel coordinates to projector pixel coordinates,
        accounting for physical height (parallax correction).
        """
        if camera_pixels.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # 1. Camera Pixels -> World (X, Y) at Z = height_mm
        world_points_2d = self.camera_model.reconstruct_world_points(
            camera_pixels, height_mm=height_mm
        )

        # 2. World (X, Y, Z) -> Projector Pixels
        N = world_points_2d.shape[0]
        world_points_3d = np.hstack(
            [world_points_2d, np.full((N, 1), height_mm)]
        )  # (N, 3)

        return self.projector_model.project_world_to_projector(world_points_3d)
