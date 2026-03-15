import logging
from typing import List, Any, Optional
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch, AppConfig
from .core.world_state import WorldState
from .constants import DEFAULT_ARUCO_MASK_COLOR


class ArucoMaskLayer(Layer):
    """
    Renders solid grey patches over detected ArUco markers to stabilize vision.
    Prevents map content from interfering with marker recognition.
    Uses parallax-corrected projection to handle markers at physical height.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config
        self._camera_matrix_inv: Optional[np.ndarray] = None
        self._R_inv: Optional[np.ndarray] = None
        self._camera_center: Optional[np.ndarray] = None

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Include enable_aruco_masking change in version
        enabled_bit = 1 if self.config.enable_aruco_masking else 0
        return (self.state.tokens_timestamp << 1) | enabled_bit

    def _update_calibration(self):
        """Pre-calculates calibration matrices for parallax correction."""
        if (
            self.config.camera_matrix is not None
            and self.config.camera_matrix.shape == (3, 3)
            and hasattr(self.config, "rvec")
            and self.config.rvec is not None
            and self.config.tvec is not None
        ):
            # Only update if rvec/tvec changed
            current_ext = (
                tuple(self.config.rvec.flatten()),
                tuple(self.config.tvec.flatten()),
            )
            if hasattr(self, "_last_ext") and self._last_ext == current_ext:
                return

            try:
                self._camera_matrix_inv = np.linalg.inv(self.config.camera_matrix)
                rvec = np.array(self.config.rvec, dtype=np.float32).reshape(3, 1)
                tvec = np.array(self.config.tvec, dtype=np.float32).reshape(3, 1)
                self._tvec = tvec
                R, _ = cv2.Rodrigues(rvec)
                self._R_inv = R.T
                # Camera center in world coordinates: C = -R^T * t
                self._camera_center = -(R.T @ tvec).flatten()
                self._last_ext = current_ext
            except Exception as e:
                self._camera_matrix_inv = None
                logging.warning(
                    f"ArucoMaskLayer: Failed to initialize parallax correction: {e}"
                )

    def _transform_pts(self, pts: Any, height_mm: float = 0.0) -> np.ndarray:
        """
        Transforms camera pixel points to projector space, accounting for height.
        Uses Projector3DModel if available and enabled.
        """
        if isinstance(pts, list):
            pts = np.array(pts, dtype=np.float32)
        else:
            pts = pts.astype(np.float32)

        # 1. Calculate World Coordinates (X, Y, height_mm) from Camera Pixels
        if self._camera_matrix_inv is not None:
            N = pts.shape[0]
            pts_homog = np.hstack([pts, np.ones((N, 1), dtype=np.float32)])  # N x 3
            rays_cam = self._camera_matrix_inv @ pts_homog.T  # 3 x N
            rays_world = self._R_inv @ rays_cam  # 3 x N

            cz = self._camera_center[2]
            vz = rays_world[2, :]
            # Intersect ray with plane Z = height_mm
            s = (height_mm - cz) / (vz + 1e-9)
            p_world = self._camera_center.reshape(3, 1) + s * rays_world  # 3 x N
            p_world = p_world.T  # N x 3
        else:
            # Fallback if camera calibration is missing (should not happen)
            p_world = np.hstack([pts, np.full((pts.shape[0], 1), height_mm)])

        # 2. Project World Points to Projector Space
        if self.config.projector_3d_model and self.config.projector_3d_model.use_3d:
            return self.config.projector_3d_model.project_world_to_projector(p_world)

        # 3. Legacy Fallback (2D Homography + Heuristic Parallax)
        if height_mm <= 0 or self._camera_matrix_inv is None:
            # Standard surface homography (Z=0)
            cam_pts = pts.reshape(-1, 1, 2).astype(np.float32).copy()
            if self.config.distortion_model:
                proj_pts = self.config.distortion_model.apply_correction(cam_pts)
            else:
                proj_pts = cv2.perspectiveTransform(
                    cam_pts, self.config.projector_matrix
                )
            return proj_pts.reshape(-1, 2)

        # Map the ground point (directly below world point) back to camera pixels
        p_world_ground = p_world.T.copy()
        p_world_ground[2, :] = 0.0
        pc = self._R_inv.T @ p_world_ground + self._tvec
        pix_ground_h = self.config.camera_matrix @ (pc / (pc[2, :] + 1e-9))
        pix_ground = pix_ground_h[:2, :].T.astype(np.float32)

        shift = pts - pix_ground
        target_pix = pts + shift * self.config.parallax_factor

        cam_pts_target = target_pix.reshape(-1, 1, 2).astype(np.float32)
        proj_pts = cv2.perspectiveTransform(
            cam_pts_target, self.config.projector_matrix
        )
        proj_pts = proj_pts.reshape(-1, 2)

        if self.config.distortion_model:
            proj_pts = self.config.distortion_model.apply_correction(
                proj_pts.reshape(-1, 1, 2)
            ).reshape(-1, 2)

        return proj_pts

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.config.enable_aruco_masking or self.state is None:
            return []

        raw_aruco = self.state.raw_aruco
        corners_list = raw_aruco.get("corners", [])
        ids = raw_aruco.get("ids", [])
        if not corners_list:
            return []

        self._update_calibration()

        logging.debug(
            f"ArucoMaskLayer: Generating patches for {len(corners_list)} markers"
        )

        patches = []
        pad = self.config.aruco_mask_padding
        color = DEFAULT_ARUCO_MASK_COLOR

        # Get token configs for height lookup
        token_profiles = getattr(self.config, "token_profiles", {})
        aruco_defaults = getattr(self.config, "aruco_defaults", {})

        default_height = 5.0

        for i, corners in enumerate(corners_list):
            marker_id = ids[i] if i < len(ids) else -1
            corners = np.array(corners, dtype=np.float32)

            # Determine height
            height_mm = default_height
            if marker_id != -1 and marker_id in aruco_defaults:
                profile_name = aruco_defaults[marker_id].profile
                if profile_name in token_profiles:
                    height_mm = token_profiles[profile_name].height_mm

            # corners is (4, 2) in camera pixel coordinates
            proj_corners = self._transform_pts(corners, height_mm=height_mm)
            proj_corners = np.array(proj_corners, dtype=np.float32).reshape(-1, 2)

            # Get bounding box in projector space
            x, y, w, h = cv2.boundingRect(proj_corners)

            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(self.config.width, x + w + pad)
            y2 = min(self.config.height, y + h + pad)

            pw, ph = x2 - x1, y2 - y1
            if pw <= 0 or ph <= 0:
                continue

            # Local coordinates for the patch
            local_corners = proj_corners - [x1, y1]

            # Create patch data (BGRA)
            patch_data = np.zeros((ph, pw, 4), dtype=np.uint8)

            # Draw polygon on a mask
            mask = np.zeros((ph, pw), dtype=np.uint8)
            cv2.fillConvexPoly(mask, local_corners.astype(np.int32), 255)

            if pad > 0:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (pad * 2 + 1, pad * 2 + 1)
                )
                mask = cv2.dilate(mask, kernel)

            # Set color and alpha
            patch_data[mask > 0, :3] = color[:3]
            patch_data[mask > 0, 3] = color[3]

            patches.append(ImagePatch(x=x1, y=y1, width=pw, height=ph, data=patch_data))

        return patches
