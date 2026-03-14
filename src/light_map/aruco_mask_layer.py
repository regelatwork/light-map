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
            try:
                self._camera_matrix_inv = np.linalg.inv(self.config.camera_matrix)
                rvec = np.array(self.config.rvec, dtype=np.float32).reshape(3, 1)
                tvec = np.array(self.config.tvec, dtype=np.float32).reshape(3, 1)
                R, _ = cv2.Rodrigues(rvec)
                self._R_inv = R.T
                # Camera center in world coordinates: C = -R^T * t
                self._camera_center = -(R.T @ tvec).flatten()
            except Exception as e:
                self._camera_matrix_inv = None
                logging.warning(
                    f"ArucoMaskLayer: Failed to initialize parallax correction: {e}"
                )

    def _transform_pts(self, pts: Any, height_mm: float = 0.0) -> np.ndarray:
        """
        Transforms camera pixel points to projector space, accounting for height.
        """
        if isinstance(pts, list):
            pts = np.array(pts, dtype=np.float32)
        else:
            pts = pts.astype(np.float32)

        if height_mm <= 0 or self._camera_matrix_inv is None:
            # Fallback to standard surface homography (Z=0)
            cam_pts = pts.reshape(-1, 1, 2).astype(np.float32).copy()
            if self.config.distortion_model:
                proj_pts = self.config.distortion_model.apply_correction(cam_pts)
            else:
                proj_pts = cv2.perspectiveTransform(
                    cam_pts, self.config.projector_matrix
                )
            return proj_pts.reshape(-1, 2)

        # Parallax Corrected Projection
        # 1. Back-project to rays in camera space
        N = pts.shape[0]
        pts_homog = np.hstack([pts, np.ones((N, 1), dtype=np.float32)])  # N x 3
        rays_cam = self._camera_matrix_inv @ pts_homog.T  # 3 x N

        # 2. Transform rays to world space
        rays_world = self._R_inv @ rays_cam  # 3 x N

        # 3. Intersect with plane Z = height_mm to get world point P
        cz = self._camera_center[2]
        vz = rays_world[2, :]
        s_marker = (height_mm - cz) / (vz + 1e-9)
        p_world_marker = (
            self._camera_center.reshape(3, 1) + s_marker * rays_world
        )  # 3 x N

        # 4. Map back to projector space.
        # projector_matrix assumed to be H from camera Z=0 to projector.
        # We need to find the camera pixel `pix_ground` that corresponds to world point [X, Y, 0].
        def world_to_pix(pw):
            R_wc = self._R_inv.T
            t_wc = np.array(self.config.tvec, dtype=np.float32).reshape(3, 1)
            pc = R_wc @ pw + t_wc
            px_h = self.config.camera_matrix @ (pc / (pc[2, :] + 1e-9))
            return px_h[:2, :].T.astype(np.float32)

        # Ground point directly below marker top
        p_world_ground = p_world_marker.copy()
        p_world_ground[2, :] = 0.0
        pix_ground = world_to_pix(p_world_ground)

        # 5. Parallax shift:
        # pts are where the marker top is seen.
        # pix_ground is where the marker bottom WOULD be seen if it were at Z=0.
        # shift = marker_top - floor_intersection
        shift = pts - pix_ground

        # factor 0.0 => use pts (Projector at Camera)
        # factor 1.0 => shift OUTWARD (Projector at half Camera height)
        # factor -1.0 => shift INWARD to floor intersection (Projector at Infinity)
        target_pix = pts + shift * self.config.parallax_factor

        # 6. Apply Homography
        cam_pts_target = target_pix.reshape(-1, 1, 2).astype(np.float32)
        proj_pts = cv2.perspectiveTransform(
            cam_pts_target, self.config.projector_matrix
        )
        proj_pts = proj_pts.reshape(-1, 2)

        # Apply non-linear distortion if present
        if self.config.distortion_model:
            corrected = []
            for p in proj_pts:
                c_p = self.config.distortion_model.correct_theoretical_point(p[0], p[1])
                corrected.append(c_p)
            proj_pts = np.array(corrected, dtype=np.float32)

        return proj_pts.reshape(-1, 2)

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

            # Get bounding box in projector space
            proj_corners_int = proj_corners.astype(np.int32)
            x, y, w, h = cv2.boundingRect(proj_corners_int)

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
