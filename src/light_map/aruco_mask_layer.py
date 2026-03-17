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
    Uses parallax-corrected projection to handle markers at physical height.
    """

    def __init__(self, state: WorldState, config: AppConfig):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.config = config

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Include enable_aruco_masking change in version
        enabled_bit = 1 if self.config.enable_aruco_masking else 0
        # Use raw_aruco_timestamp to ensure masks persist even if logical tokens change
        return (self.state.raw_aruco_timestamp << 1) | enabled_bit

    def _transform_pts(self, pts: Any, height_mm: float = 0.0) -> np.ndarray:
        """
        Transforms camera pixel points to projector space.
        Outputs coordinates in Calibration Space (e.g. 4608x2592).
        """
        if isinstance(pts, list):
            pts = np.array(pts, dtype=np.float32)
        else:
            pts = pts.astype(np.float32)

        # 1. Project to World Space (X, Y, height_mm)
        projection_model = self.config.camera_projection_model
        if projection_model is not None:
            world_pts = projection_model.reconstruct_world_points(pts, height_mm)
            wx_mm = world_pts[:, 0]
            wy_mm = world_pts[:, 1]
        else:
            # Fallback if camera calibration missing: assume identity mm mapping
            # This allows unit tests without full calibration to still pass.
            wx_mm = pts[:, 0]
            wy_mm = pts[:, 1]

        # 2. Map World (mm) to Projector Pixels (Calibration Space)
        ppi = self.config.projector_ppi
        ppi_mm = ppi / 25.4 if ppi > 0 else 0.0

        px = wx_mm * ppi_mm
        py = wy_mm * ppi_mm

        proj_pts = np.column_stack([px, py]).astype(np.float32)

        # 3. Apply Distortion Model if available
        if self.config.distortion_model:
            corrected = []
            for pt in proj_pts:
                c_px, c_py = self.config.distortion_model.correct_theoretical_point(
                    pt[0], pt[1]
                )
                corrected.append([c_px, c_py])
            proj_pts = np.array(corrected, dtype=np.float32)

        return proj_pts

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if not self.config.enable_aruco_masking or self.state is None:
            return []

        raw_aruco = self.state.raw_aruco
        corners_list = raw_aruco.get("corners", [])
        ids = raw_aruco.get("ids", [])
        if not corners_list:
            return []

        patches = []
        pad = self.config.aruco_mask_padding
        color = DEFAULT_ARUCO_MASK_COLOR

        # Calibration resolution for clamping
        calib_w, calib_h = self.config.projector_matrix_resolution
        limit_w = calib_w if calib_w > 0 else self.config.width
        limit_h = calib_h if calib_h > 0 else self.config.height

        logging.debug(
            f"ArucoMaskLayer: Generating patches for {len(corners_list)} markers. Range: {limit_w}x{limit_h}"
        )

        default_height = 5.0

        for i, corners in enumerate(corners_list):
            marker_id = ids[i] if i < len(ids) else -1
            corners = np.array(corners, dtype=np.float32)

            # Determine height
            height_mm = default_height
            if marker_id != -1 and marker_id in getattr(
                self.config, "aruco_defaults", {}
            ):
                profile_name = self.config.aruco_defaults[marker_id].profile
                if profile_name in getattr(self.config, "token_profiles", {}):
                    height_mm = self.config.token_profiles[profile_name].height_mm

            # corners is (4, 2) in camera pixel coordinates
            proj_corners = self._transform_pts(corners, height_mm=height_mm)
            proj_corners = np.array(proj_corners, dtype=np.float32).reshape(-1, 2)

            # Get bounding box in projector space
            x, y, w, h = cv2.boundingRect(proj_corners)

            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(limit_w, x + w + pad)
            y2 = min(limit_h, y + h + pad)

            pw, ph = int(x2 - x1), int(y2 - y1)
            if pw <= 0 or ph <= 0:
                logging.debug(
                    f"ArucoMaskLayer: Marker {marker_id} off-limits: x1={x1}, y1={y1}, x2={x2}, y2={y2}"
                )
                continue

            logging.debug(
                f"ArucoMaskLayer: Final patch for marker {marker_id}: x={x1}, y={y1}, w={pw}, h={ph}"
            )

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

            patches.append(
                ImagePatch(x=int(x1), y=int(y1), width=pw, height=ph, data=patch_data)
            )

        return patches
