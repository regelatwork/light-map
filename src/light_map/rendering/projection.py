import logging
import os
from typing import Any

import cv2
import numpy as np

from light_map.core.common_types import ProjectorPose


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

    def reconstruct_world_points_3d(
        self, pixel_points: np.ndarray, height_mm: float = 0.0
    ) -> np.ndarray:
        """
        Intersects rays from the camera through pixel_points with the plane Z = height_mm.
        Returns (N, 3) array of [X, Y, Z] world coordinates.
        """
        if pixel_points.size == 0:
            return np.zeros((0, 3), dtype=np.float32)

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

        # 3. Intersect rays with plane Z = 0 to get ground points P0
        # P0 = C + s0 * world_rays
        # P0.z = 0  => s0 = -C.z / world_rays.z
        camera_center_z = self.camera_center[2]
        world_rays_z = world_rays[2, :]
        s0 = -camera_center_z / (world_rays_z + 1e-9)
        p0 = self.camera_center.reshape(3, 1) + s0 * world_rays

        # 4. Use similar triangles to find point P at physical height_mm
        # P = p0 + (height_mm / |C.z|) * (C - p0)
        # This moves the point from the ground towards the camera.
        # This formulation is robust to Z-axis orientation.
        world_points_3d = p0 + (height_mm / (np.abs(camera_center_z) + 1e-9)) * (
            self.camera_center.reshape(3, 1) - p0
        )

        return world_points_3d.T.astype(np.float32)

    def reconstruct_world_points(
        self, pixel_points: np.ndarray, height_mm: float = 0.0
    ) -> np.ndarray:
        """
        Reconstructs the (X, Y) world coordinates for objects seen at pixel_points,
        assuming they are at physical height_mm.
        Returns (N, 2) array of [X, Y] world coordinates.
        """
        res_3d = self.reconstruct_world_points_3d(pixel_points, height_mm=height_mm)
        return res_3d[:, :2].astype(np.float32)

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
        intrinsic_matrix: np.ndarray | None = None,
        distortion_coefficients: np.ndarray | None = None,
        rotation_vector: np.ndarray | None = None,
        translation_vector: np.ndarray | None = None,
        homography_matrix: np.ndarray | None = None,
        use_3d: bool = False,
    ):
        self.intrinsic_matrix = intrinsic_matrix
        self.distortion_coefficients = distortion_coefficients
        self.rotation_vector = rotation_vector
        self.translation_vector = translation_vector
        self.homography_matrix = homography_matrix
        self.use_3d = use_3d

        self.calibrated_projector_center = None
        if self.rotation_vector is not None and self.translation_vector is not None:
            R, _ = cv2.Rodrigues(self.rotation_vector)
            self.calibrated_projector_center = -(
                R.T @ self.translation_vector.flatten()
            )

    def get_projector_center(
        self, override: ProjectorPose | None = None
    ) -> np.ndarray | None:
        """Returns the absolute 3D position of the projector center."""
        if override is not None:
            return np.array([override.x, override.y, override.z], dtype=np.float32)
        return self.calibrated_projector_center

    @property
    def projector_center(self) -> np.ndarray | None:
        """Legacy property for backward compatibility (no override)."""
        return self.calibrated_projector_center

    @property
    def is_calibrated_3d(self) -> bool:
        """Returns True if full 3D calibration data is present."""
        return self.intrinsic_matrix is not None and self.rotation_vector is not None

    def project_world_to_projector(
        self,
        world_points: np.ndarray,
        projector_pose: ProjectorPose | None = None,
    ) -> np.ndarray:
        """
        Maps (N, 3) World points to (N, 2) Projector pixels.
        If use_3d and 3D calibration is present, it uses full projective transformation.
        Otherwise, returns world points (X, Y) as pixels, which is usually incorrect
        unless world units are pixels and origin matches.
        """
        if (
            self.use_3d
            and self.intrinsic_matrix is not None
            and self.rotation_vector is not None
        ):
            # 1. Determine Pose
            rv = self.rotation_vector
            tv = self.translation_vector

            if projector_pose is not None:
                # Calculate adjusted translation vector: t = -R * C
                R, _ = cv2.Rodrigues(rv)
                C = np.array(
                    [projector_pose.x, projector_pose.y, projector_pose.z],
                    dtype=np.float32,
                )
                tv = -(R @ C).reshape(3, 1)

            # Full 3D Projective transformation
            projector_pixels, _ = cv2.projectPoints(
                world_points.astype(np.float32),
                rv,
                tv,
                self.intrinsic_matrix,
                self.distortion_coefficients,
            )
            return projector_pixels.reshape(-1, 2)
        else:
            # We NO LONGER fall back to homography here because the homography
            # in this model is typically Camera-to-Projector, NOT World-to-Projector.
            # ProjectionService handles the fallback by applying homography to camera pixels.
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
        self,
        camera_model: CameraProjectionModel,
        projector_model: Projector3DModel,
        ppi: float = 0.0,
        distortion_model: Any | None = None,
    ):
        self.camera_model = camera_model
        self.projector_model = projector_model
        self.ppi = ppi
        self.distortion_model = distortion_model

    def project_camera_to_projector(
        self,
        camera_pixels: np.ndarray,
        height_mm: float = 0.0,
        target_z: float | None = None,
        prefer_homography: bool = True,
        projector_pose: ProjectorPose | None = None,
    ) -> np.ndarray:
        """
        Maps camera pixel coordinates to projector pixel coordinates with parallax correction.

        Args:
            camera_pixels: (N, 2) array of camera pixel coordinates.
            height_mm: The physical height of the object seen at camera_pixels.
            target_z: The physical height where the projector should hit.
                     If None, it defaults to height_mm (hits the object).
                     If 0.0, it hits the ground directly under the object.
            prefer_homography: If True, uses the 2D homography (with parallax correction)
                               instead of the 3D projective model.
            projector_pose: Optional absolute 3D position override for the projector.
        """
        if camera_pixels.size == 0:
            return np.zeros((0, 2), dtype=np.float32)

        # 1. Reconstruct Object Position in 3D (at height_mm)
        # This gives us the true (X, Y) where the object actually is.
        # It uses the robust reconstruct_world_points_3d which handles C.z sign.
        marker_pts_3d = self.camera_model.reconstruct_world_points_3d(
            camera_pixels, height_mm=height_mm
        )

        # 2. Define the 3D Target Point (at target_z)
        # We want to hit the spot directly under/over the marker at target_z.
        target_pts_3d = marker_pts_3d.copy()

        if target_z is not None:
            # If target_z is provided (e.g. 0.0 for floor), we ensure it has the correct sign.
            # Most users provide positive heights, but if C.z is negative, Z is negative.
            target_pts_3d[:, 2] = (
                np.sign(self.camera_model.camera_center[2]) * target_z
                if target_z != 0
                else 0.0
            )
        # else: target_z is None, so we hit the object at its reconstructed Z (e.g. at height_mm)

        # 3. Use 3D Projective Model if preferred and available
        if (
            not prefer_homography
            and self.projector_model.is_calibrated_3d
            and self.projector_model.use_3d
        ):
            return self.projector_model.project_world_to_projector(target_pts_3d)

        # 4. Use 2D Homography or PPI-based projection (with parallax correction)
        # To hit target_pts_3d using a floor-based (Z=0) mapping, we find where
        # the projector ray through target_pts_3d would hit the floor.
        proj_pos = self.projector_model.get_projector_center(override=projector_pose)
        if proj_pos is None:
            # Fallback to co-located assumption
            proj_pos = self.camera_model.camera_center

        pj_z = proj_pos[2]

        # Parallax factor calculation
        # We want pm0 = proj_pos + s * (target_pts_3d - proj_pos) such that pm0.z = 0.
        # s = -pj_z / (target_pts_3d.z - pj_z)
        # C in pm0 = target_pts_3d + (target_pts_3d - proj_pos) * C
        # s = 1 + C => C = s - 1 = -pj_z / (target_pts_3d.z - pj_z) - 1
        # C = (-pj_z - (target_pts_3d.z - pj_z)) / (target_pts_3d.z - pj_z)
        # C = -target_pts_3d.z / (target_pts_3d.z - pj_z)
        # If target_pts_3d.z and pj_z are same sign (e.g. negative), this works.
        denominator = target_pts_3d[:, 2] - pj_z
        C = -target_pts_3d[:, 2] / (denominator + 1e-9)

        # Reshape C for broadcasting (N, 1)
        C = C.reshape(-1, 1)
        pm0 = target_pts_3d + (target_pts_3d - proj_pos.reshape(1, 3)) * C

        # A. Use Homography if available (maps Camera at Z=0 to Projector)
        if self.projector_model.homography_matrix is not None:
            # Map the floor point P back to the camera pixel that sees it
            ground_camera_pixels = self.camera_model.project_world_to_camera(pm0)

            camera_pixels_reshaped = ground_camera_pixels.reshape(-1, 1, 2).astype(
                np.float32
            )
            # Apply homography and optional 2D distortion correction
            if self.distortion_model:
                proj_pts = self.distortion_model.apply_correction(
                    camera_pixels_reshaped
                )
            else:
                proj_pts = cv2.perspectiveTransform(
                    camera_pixels_reshaped, self.projector_model.homography_matrix
                )
            return proj_pts.reshape(-1, 2)

        # B. PPI-based fallback (Assumes orthographic projector alignment)
        if self.ppi > 0:
            ppi_mm = self.ppi / 25.4
            px = pm0[:, 0] * ppi_mm
            py = pm0[:, 1] * ppi_mm
            pts = np.vstack([px, py]).T
            if self.distortion_model:
                # Distortion model expects (N, 1, 2) but we can use correct_theoretical_point loop
                res = []
                for p in pts:
                    rx, ry = self.distortion_model.correct_theoretical_point(p[0], p[1])
                    res.append([rx, ry])
                return np.array(res, dtype=np.float32)
            return pts.astype(np.float32)

        # 5. Last Fallback: Just return target world points (not floor intersection)
        return target_pts_3d[:, :2].astype(np.float32)
