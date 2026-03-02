import cv2
import numpy as np
import os
import logging
from typing import List, Tuple, Optional, Dict, Any, TYPE_CHECKING
from light_map.common_types import Token
from light_map.map_system import MapSystem

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel


class ArucoTokenDetector:
    def __init__(
        self,
        calibration_file: str = "camera_calibration.npz",
        extrinsics_file: str = "camera_extrinsics.npz",
        dictionary_type: int = cv2.aruco.DICT_4X4_50,
        debug_mode: bool = False,
    ):
        self.debug_mode = debug_mode
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvec = None
        self.tvec = None
        self.R = None
        self.camera_center_world = None

        # Performance optimization
        self.target_width = 1920
        self._fov_mask = None
        self._fov_mask_params = None

        # Load calibration
        if os.path.exists(calibration_file):
            data = np.load(calibration_file)
            self.camera_matrix = data["camera_matrix"]
            self.dist_coeffs = data["dist_coeffs"]
            logging.info("ArucoDetector: Loaded camera calibration.")
        else:
            logging.warning("ArucoDetector: Camera calibration file not found.")

        # Load extrinsics
        if os.path.exists(extrinsics_file):
            data = np.load(extrinsics_file)
            self.rvec = data["rvec"]
            self.tvec = data["tvec"]
            self.R, _ = cv2.Rodrigues(self.rvec)
            # Camera center in world coordinates: C = -R^T * t
            self.camera_center_world = -self.R.T @ self.tvec.flatten()
            logging.info("ArucoDetector: Loaded camera extrinsics.")
        else:
            logging.warning("ArucoDetector: Camera extrinsics file not found.")

        # Initialize ArUco detector
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_type)
        parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    def set_calibration(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        logging.debug("ArucoDetector: Camera intrinsics updated.")

    def set_extrinsics(self, rvec: np.ndarray, tvec: np.ndarray):
        self.rvec = rvec
        self.tvec = tvec
        self.R, _ = cv2.Rodrigues(self.rvec)
        # Camera center in world coordinates: C = -R^T * t
        self.camera_center_world = -self.R.T @ self.tvec.flatten()
        logging.debug("ArucoDetector: Camera extrinsics updated.")

    def get_fov_roi(
        self,
        frame_shape: Tuple[int, int],
        scale: float,
        projector_matrix: np.ndarray,
        map_dims: Tuple[int, int],
    ) -> Optional[Tuple[int, int, int, int]]:
        """Returns (x, y, w, h) bounding box of the FOV mask."""
        mask = self._get_fov_mask(frame_shape, scale, projector_matrix, map_dims)
        if mask is None:
            return None
        return cv2.boundingRect(mask)

    def detect_raw(
        self,
        frame: np.ndarray,
        projector_matrix: Optional[np.ndarray] = None,
        map_dims: Optional[Tuple[int, int]] = None,
        crop_offset: Optional[Tuple[int, int]] = None,
    ) -> Tuple[List[np.ndarray], List[int]]:
        """
        Detects ArUco markers, handles resizing, FOV masking, and duplicate resolution.
        If crop_offset=(x, y) is provided, it assumes frame is already cropped.
        """
        h_orig, w_orig = frame.shape[:2]

        # 1. Handle Resizing
        scale = 1.0
        if self.target_width > 0 and w_orig > self.target_width and crop_offset is None:
            scale = self.target_width / w_orig
            new_h = int(h_orig * scale)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (self.target_width, new_h))
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        offset_x, offset_y = crop_offset if crop_offset else (0, 0)

        # 2. FOV Masking (if not already cropped)
        if (
            crop_offset is None
            and projector_matrix is not None
            and map_dims is not None
        ):
            mask = self._get_fov_mask(
                gray.shape,
                scale,
                projector_matrix,
                map_dims,
            )
            if mask is not None:
                x, y, w, h = cv2.boundingRect(mask)
                if w > 0 and h > 0:
                    gray = gray[y : y + h, x : x + w]
                    mask = mask[y : y + h, x : x + w]
                    gray = cv2.bitwise_and(gray, mask)
                    offset_x, offset_y = x, y

        # 3. Detect
        corners, ids, rejected = self.detector.detectMarkers(gray)

        if ids is None:
            return [], []

        # 4. Process Detections
        # Group by ID and find best marker (largest area)
        detections_by_id = {}
        for i, marker_id_arr in enumerate(ids):
            marker_id = int(marker_id_arr[0])
            # corners[i] is (1, 4, 2)
            marker_corners = corners[i][0].copy()

            # Add crop offset (in current potentially scaled space)
            if offset_x != 0 or offset_y != 0:
                marker_corners[:, 0] += offset_x
                marker_corners[:, 1] += offset_y

            # Scale back to original resolution
            if scale != 1.0:
                marker_corners = marker_corners / scale

            area = cv2.contourArea(marker_corners)
            if (
                marker_id not in detections_by_id
                or area > detections_by_id[marker_id]["area"]
            ):
                detections_by_id[marker_id] = {"corners": marker_corners, "area": area}

        final_corners = [v["corners"] for v in detections_by_id.values()]
        final_ids = [k for k in detections_by_id.keys()]

        return final_corners, final_ids

    def map_to_tokens(
        self,
        raw_data: Dict[str, Any],
        map_system: MapSystem,
        token_configs: Dict[int, Dict] = None,
        ppi: float = 96.0,
        default_height_mm: float = 5.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        """
        Maps raw ArUco detections (corners, ids) to Token objects in world coordinates.
        """
        if self.camera_matrix is None or self.R is None:
            return []

        corners = raw_data.get("corners", [])
        ids = raw_data.get("ids", [])

        if not ids:
            return []

        tokens = []
        ppi_mm = ppi / 25.4 if ppi > 0 else 0.0

        for i, marker_id in enumerate(ids):
            marker_corners = np.array(corners[i])
            u, v = np.mean(marker_corners, axis=0)

            # Apply parallax correction
            height_mm = default_height_mm
            if token_configs and marker_id in token_configs:
                height_mm = token_configs[marker_id].get("height_mm", default_height_mm)

            wx_mm, wy_mm = self._parallax_correction(u, v, height_mm)

            # Map to projector pixels (Z=0 vertical projection)
            px = wx_mm * ppi_mm
            py = wy_mm * ppi_mm

            if distortion_model:
                px, py = distortion_model.correct_theoretical_point(px, py)

            # Map to SVG units
            wx_svg, wy_svg = map_system.screen_to_world(px, py)

            tokens.append(
                Token(
                    id=marker_id,
                    world_x=wx_svg,
                    world_y=wy_svg,
                    world_z=0.0,
                    marker_x=wx_svg,
                    marker_y=wy_svg,
                    marker_z=height_mm,
                    confidence=1.0,
                    is_duplicate=False,  # detect_raw already resolved duplicates
                )
            )

        return tokens

    def detect(
        self,
        frame: np.ndarray,
        map_system: MapSystem,
        token_configs: Dict[int, Dict] = None,
        ppi: float = 96.0,
        default_height_mm: float = 5.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
        projector_matrix: Optional[np.ndarray] = None,
    ) -> List[Token]:
        """
        Legacy/Combined method for single-threaded use.
        """
        corners, ids = self.detect_raw(
            frame,
            projector_matrix=projector_matrix,
            map_dims=(map_system.width, map_system.height),
        )
        return self.map_to_tokens(
            {"corners": corners, "ids": ids},
            map_system,
            token_configs=token_configs,
            ppi=ppi,
            default_height_mm=default_height_mm,
            distortion_model=distortion_model,
        )

    def _get_fov_mask(
        self,
        gray_shape: Tuple[int, int],
        scale: float,
        projector_matrix: np.ndarray,
        map_dims: Tuple[int, int],
    ) -> Optional[np.ndarray]:
        """Caches and returns the projector FOV mask."""
        h, w = gray_shape
        params = (h, w, scale, hash(projector_matrix.tobytes()), map_dims)

        if self._fov_mask is not None and self._fov_mask_params == params:
            return self._fov_mask

        w_proj, h_proj = map_dims
        try:
            # projector_matrix maps from projector to camera coordinates
            proj_corners = np.array(
                [[0, 0], [w_proj, 0], [w_proj, h_proj], [0, h_proj]],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            cam_corners = cv2.perspectiveTransform(proj_corners, projector_matrix)

            # Adjust corners for scaled detection frame
            if scale != 1.0:
                cam_corners *= scale

            cam_corners = cam_corners.astype(np.int32)

            mask = np.zeros(gray_shape, dtype=np.uint8)
            cv2.fillConvexPoly(mask, cam_corners, 255)
            self._fov_mask = mask
            self._fov_mask_params = params
            return mask
        except Exception:
            return None

    def _parallax_correction(self, u: float, v: float, h: float) -> Tuple[float, float]:
        """
        Intersects the ray from camera through (u, v) with the plane z = h.
        Returns (X, Y) in world space.
        """
        if self.camera_matrix is None or self.R is None:
            return 0.0, 0.0

        # 1. Back-project to ray in camera space
        # [u, v, 1] in pixels -> ray in camera space
        # Ray direction: inv(K) * [u, v, 1]^T
        p_pixel = np.array([u, v, 1.0]).reshape(3, 1)
        ray_cam = np.linalg.inv(self.camera_matrix) @ p_pixel

        # 2. Transform ray to world space
        # v_world = R^T * ray_cam
        v_world = self.R.T @ ray_cam
        v_world = v_world.flatten()

        # 3. Intersect with plane z = h
        # P = C + s * v_world
        # P.z = C.z + s * v_world.z = h
        # s = (h - C.z) / v_world.z

        cz = self.camera_center_world[2]
        vz = v_world[2]

        if abs(vz) < 1e-6:
            if self.debug_mode:
                logging.debug(f"Parallax: vz={vz:.6f} too small, returning (0,0)")
            return 0.0, 0.0  # Should not happen if camera is above table

        s = (h - cz) / vz
        if s < 0:
            if self.debug_mode:
                logging.debug(
                    f"Parallax: s={s:.1f} is negative (impossible ray), returning (0,0)"
                )
            return 0.0, 0.0

        p_world = self.camera_center_world + s * v_world

        if self.debug_mode:
            logging.debug(
                f"Parallax: u,v=({u:.1f}, {v:.1f}) h={h:.1f} s={s:.1f} cz={cz:.1f} vz={vz:.3f} p_world=({p_world[0]:.1f}, {p_world[1]:.1f}, {p_world[2]:.1f})"
            )

        return p_world[0], p_world[1]
