import logging
from typing import List
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch, AppConfig
from .core.world_state import WorldState
from .vision.hand_masker import HandMasker


class HandMaskLayer(Layer):
    """
    Renders black patches over hand regions to prevent projection on hands.
    Uses HandMasker for geometry and focusing strictly on rendering.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config
        self.hand_masker = HandMasker()

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # If we have active hulls, we are dynamic (rendering every frame for persistence)
        self._is_dynamic = bool(self.hand_masker.last_hulls)

        # Include enable_hand_masking change in version
        return (self.state.hands_timestamp << 1) | (
            1 if self.config.enable_hand_masking else 0
        )

    def _transform_pts(self, pts: np.ndarray) -> np.ndarray:
        """Helper to transform normalized camera points to projector space."""
        cam_pts = pts.reshape(-1, 2).copy()

        # Denormalize based on camera frame size
        frame_h, frame_w = (1080, 1920)  # Standard fallback
        if self.state.background is not None:
            frame_h, frame_w = self.state.background.shape[:2]

        cam_pts[:, 0] *= frame_w
        cam_pts[:, 1] *= frame_h

        # If using 3D model, we need to assume a Z-height for hands.
        # For now, let's assume Z=0 (tabletop) or a slight offset.
        if self.config.projector_3d_model and self.config.projector_3d_model.use_3d:
            # Note: The Projector3DModel.project_world_to_projector expects WORLD points.
            # Here cam_pts are CAMERA pixels. We need to convert CAMERA pixels to WORLD.

            # TODO: Move the world_to_pix / pix_to_world logic into a centralized VisionService.
            # For now, if we have extrinsics, we can reconstruct world points at Z=0.
            if (
                hasattr(self.config, "camera_matrix")
                and self.config.camera_matrix is not None
                and self.config.rotation_vector is not None
                and self.config.translation_vector is not None
            ):
                try:
                    camera_matrix_inv = np.linalg.inv(self.config.camera_matrix)
                    rotation_vector = np.array(self.config.rotation_vector).reshape(
                        3, 1
                    )
                    translation_vector = np.array(
                        self.config.translation_vector
                    ).reshape(3, 1)
                    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
                    rotation_matrix_inv = rotation_matrix.T
                    camera_center = -(
                        rotation_matrix_inv @ translation_vector
                    ).flatten()

                    pts_homog = np.hstack([cam_pts, np.ones((cam_pts.shape[0], 1))])
                    rays_cam = camera_matrix_inv @ pts_homog.T
                    rays_world = rotation_matrix_inv @ rays_cam

                    camera_center_z = camera_center[2]
                    rays_world_z = rays_world[2, :]
                    s = (0.0 - camera_center_z) / (rays_world_z + 1e-9)
                    p_world = camera_center.reshape(3, 1) + s * rays_world
                    return self.config.projector_3d_model.project_world_to_projector(
                        p_world.T
                    )
                except Exception as e:
                    logging.warning(f"HandMaskLayer: 3D projection failed: {e}")

        # Fallback to standard surface homography (Z=0)
        cam_pts_reshaped = cam_pts.reshape(-1, 1, 2).astype(np.float32)
        if self.config.distortion_model:
            proj_pts = self.config.distortion_model.apply_correction(cam_pts_reshaped)
        else:
            proj_pts = cv2.perspectiveTransform(
                cam_pts_reshaped, self.config.projector_matrix
            )
        return proj_pts.reshape(-1, 2)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.config.enable_hand_masking:
            return []

        if self.state is None:
            return []

        # Get hulls from masker (delegates transform logic)
        hulls = self.hand_masker.get_mask_hulls(
            self.state.hands, self._transform_pts, current_time
        )

        if not hulls:
            return []

        patches = []
        # Calculate padding in pixels for a 2cm radius
        padding_2cm = int(0.7874 * self.config.projector_ppi)

        for hull in hulls:
            x, y, w, h = cv2.boundingRect(hull)

            # Apply padding to the bounding box
            pad = padding_2cm + 20  # extra margin for blur
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(self.config.width, x + w + pad)
            y2 = min(self.config.height, y + h + pad)

            pw, ph = x2 - x1, y2 - y1
            if pw <= 0 or ph <= 0:
                continue

            # Create local patch
            local_hull = hull - [x1, y1]

            # Draw hull mask on patch
            mask_patch = np.zeros((ph, pw), dtype=np.uint8)
            cv2.drawContours(
                mask_patch,
                [local_hull.astype(np.int32)],
                -1,
                255,
                thickness=padding_2cm * 2,
            )
            cv2.fillPoly(mask_patch, [local_hull.astype(np.int32)], 255)

            patch_data = np.zeros((ph, pw, 4), dtype=np.uint8)
            patch_data[:, :, 3] = mask_patch  # RGB is 0 (Black)

            patches.append(ImagePatch(x=x1, y=y1, width=pw, height=ph, data=patch_data))

        return patches
