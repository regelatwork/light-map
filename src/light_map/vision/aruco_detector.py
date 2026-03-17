import cv2
import numpy as np
import os
import logging
from typing import List, Tuple, Optional, Dict, Any, TYPE_CHECKING
from light_map.common_types import Token
from light_map.map_system import MapSystem
from light_map.vision.projection import CameraProjectionModel

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel
    from light_map.vision.projection import Projector3DModel


class ArucoTokenDetector:
    def __init__(
        self,
        calibration_file: Optional[str] = None,
        extrinsics_file: Optional[str] = None,
        dictionary_type: int = cv2.aruco.DICT_4X4_50,
        debug_mode: bool = False,
    ):
        self.debug_mode = debug_mode
        self.camera_matrix: Optional[np.ndarray] = None
        self.distortion_coefficients: Optional[np.ndarray] = None
        self.rotation_vector: Optional[np.ndarray] = None
        self.translation_vector: Optional[np.ndarray] = None
        self.projection_model: Optional[CameraProjectionModel] = None

        # Performance optimization
        self.target_width = 1920
        self._fov_mask = None
        self._fov_mask_params = None

        # Load calibration
        if calibration_file:
            if os.path.exists(calibration_file):
                data = np.load(calibration_file)
                self.camera_matrix = data["camera_matrix"]
                self.distortion_coefficients = data.get("distortion_coefficients")
                if self.distortion_coefficients is None:
                    self.distortion_coefficients = data.get("dist_coeffs")
                logging.info(
                    f"ArucoDetector: Loaded camera calibration from {calibration_file}."
                )
            else:
                logging.warning(
                    f"ArucoDetector: Camera calibration file '{calibration_file}' not found."
                )

        # Load extrinsics
        if extrinsics_file:
            if os.path.exists(extrinsics_file):
                data = np.load(extrinsics_file)
                rotation_vector = data.get("rotation_vector")
                if rotation_vector is None:
                    rotation_vector = data.get("rvec")
                translation_vector = data.get("translation_vector")
                if translation_vector is None:
                    translation_vector = data.get("tvec")
                self.set_extrinsics(rotation_vector, translation_vector)
                logging.info(
                    f"ArucoDetector: Loaded camera extrinsics from {extrinsics_file}."
                )
            else:
                logging.warning(
                    f"ArucoDetector: Camera extrinsics file '{extrinsics_file}' not found."
                )

        # Initialize ArUco detector
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_type)
        parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    def set_calibration(
        self, camera_matrix: np.ndarray, distortion_coefficients: np.ndarray
    ):
        self.camera_matrix = camera_matrix
        self.distortion_coefficients = distortion_coefficients
        self._update_projection_model()
        logging.debug("ArucoDetector: Camera intrinsics updated.")

    def set_extrinsics(
        self, rotation_vector: np.ndarray, translation_vector: np.ndarray
    ):
        self.rotation_vector = rotation_vector
        self.translation_vector = translation_vector
        self._update_projection_model()
        logging.debug("ArucoDetector: Camera extrinsics updated.")

    def _update_projection_model(self):
        """Updates the shared projection model if all calibration is present."""
        if (
            self.camera_matrix is not None
            and self.rotation_vector is not None
            and self.translation_vector is not None
        ):
            self.projection_model = CameraProjectionModel(
                self.camera_matrix,
                self.distortion_coefficients,
                self.rotation_vector,
                self.translation_vector,
            )

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
        projector_3d_model: Optional["Projector3DModel"] = None,
    ) -> List[Token]:
        """
        Maps raw ArUco detections (corners, ids) to Token objects in world coordinates.
        """
        if self.projection_model is None:
            logging.debug("ArucoDetector: map_to_tokens missing projection model.")
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
            token_type = "NPC"
            if token_configs and marker_id in token_configs:
                config = token_configs[marker_id]
                height_mm = config.get("height_mm", default_height_mm)
                token_type = config.get("type", "NPC")

            # Vectorized model handles single points efficiently
            pixel_points = np.array([[u, v]], dtype=np.float32)
            world_points = self.projection_model.reconstruct_world_points(
                pixel_points, height_mm
            )
            world_x_mm, world_y_mm = world_points[0]

            logging.debug(
                f"ArucoDetector: Marker {marker_id} at cam {u:.1f},{v:.1f} -> world {world_x_mm:.1f},{world_y_mm:.1f} (h={height_mm})"
            )

            if projector_3d_model and projector_3d_model.use_3d:
                world_points_3d = np.array(
                    [[world_x_mm, world_y_mm, height_mm]], dtype=np.float32
                )
                projector_pixels = projector_3d_model.project_world_to_projector(
                    world_points_3d
                )[0]
                px, py = projector_pixels[0], projector_pixels[1]
                logging.debug(
                    f"ArucoDetector: Marker {marker_id} 3D projection -> proj {px:.1f},{py:.1f}"
                )
            else:
                # Map to projector pixels (Z=0 vertical projection)
                px = world_x_mm * ppi_mm
                py = world_y_mm * ppi_mm
                logging.debug(
                    f"ArucoDetector: Marker {marker_id} 2D map -> proj {px:.1f},{py:.1f} (ppi_mm={ppi_mm:.2f})"
                )

                if distortion_model:
                    orig_px, orig_py = px, py
                    px, py = distortion_model.correct_theoretical_point(px, py)
                    logging.debug(
                        f"ArucoDetector: Marker {marker_id} distortion correction: {orig_px:.1f},{orig_py:.1f} -> {px:.1f},{py:.1f}"
                    )

            # Map to SVG units
            wx_svg, wy_svg = map_system.screen_to_world(px, py)
            logging.debug(
                f"ArucoDetector: Marker {marker_id} final screen {px:.1f},{py:.1f} -> SVG {wx_svg:.1f},{wy_svg:.1f}"
            )

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
                    type=token_type,
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
        projector_3d_model: Optional["Projector3DModel"] = None,
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
            projector_3d_model=projector_3d_model,
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
            # projector_matrix maps from camera to projector.
            # We need to map projector corners (0,0, w, h) BACK to camera space
            # to define the FOV mask in the camera frame.
            inv_h = np.linalg.inv(projector_matrix)

            proj_corners = np.array(
                [[0, 0], [w_proj, 0], [w_proj, h_proj], [0, h_proj]],
                dtype=np.float32,
            ).reshape(-1, 1, 2)
            cam_corners = cv2.perspectiveTransform(proj_corners, inv_h)

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
