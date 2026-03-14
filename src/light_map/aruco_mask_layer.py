import logging
from typing import List, Any
import cv2
import numpy as np
from .common_types import Layer, LayerMode, ImagePatch, AppConfig
from .core.world_state import WorldState
from .constants import DEFAULT_ARUCO_MASK_COLOR


class ArucoMaskLayer(Layer):
    """
    Renders solid grey patches over detected ArUco markers to stabilize vision.
    Prevents map content from interfering with marker recognition.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Include enable_aruco_masking change in version
        enabled_bit = 1 if self.config.enable_aruco_masking else 0
        return (self.state.tokens_timestamp << 1) | enabled_bit

    def _transform_pts(self, pts: Any) -> np.ndarray:
        """Helper to transform camera pixel points to projector space."""
        # pts is expected to be (N, 2)
        if isinstance(pts, list):
            pts = np.array(pts, dtype=np.float32)

        cam_pts = pts.reshape(-1, 1, 2).astype(np.float32).copy()

        if self.config.distortion_model:
            proj_pts = self.config.distortion_model.apply_correction(cam_pts)
        else:
            proj_pts = cv2.perspectiveTransform(cam_pts, self.config.projector_matrix)

        return proj_pts.reshape(-1, 2)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.config.enable_aruco_masking or self.state is None:
            return []

        raw_aruco = self.state.raw_aruco
        corners_list = raw_aruco.get("corners", [])
        if not corners_list:
            return []

        logging.debug(
            f"ArucoMaskLayer: Generating patches for {len(corners_list)} markers"
        )

        patches = []
        pad = self.config.aruco_mask_padding
        color = DEFAULT_ARUCO_MASK_COLOR

        for corners in corners_list:
            # corners is (4, 2) in camera pixel coordinates
            proj_corners = self._transform_pts(corners)

            # Get bounding box in projector space
            # Using int32 for cv2.boundingRect
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
                # Expand the mask by pad pixels using dilation
                # A circular kernel is better for uniform padding
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (pad * 2 + 1, pad * 2 + 1)
                )
                mask = cv2.dilate(mask, kernel)

            # Set color and alpha
            patch_data[mask > 0, :3] = color[:3]
            patch_data[mask > 0, 3] = color[3]

            patches.append(ImagePatch(x=x1, y=y1, width=pw, height=ph, data=patch_data))

        return patches
