import cv2
import numpy as np
import os
from typing import List, Tuple, Optional, Dict, TYPE_CHECKING
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

        # Load calibration
        if os.path.exists(calibration_file):
            data = np.load(calibration_file)
            self.camera_matrix = data["camera_matrix"]
            self.dist_coeffs = data["dist_coeffs"]

        # Load extrinsics
        if os.path.exists(extrinsics_file):
            data = np.load(extrinsics_file)
            self.rvec = data["rvec"]
            self.tvec = data["tvec"]
            self.R, _ = cv2.Rodrigues(self.rvec)
            # Camera center in world coordinates: C = -R^T * t
            self.camera_center_world = -self.R.T @ self.tvec.flatten()

        # Initialize ArUco detector
        dictionary = cv2.aruco.getPredefinedDictionary(dictionary_type)
        parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    def detect(
        self,
        frame: np.ndarray,
        map_system: MapSystem,
        token_configs: Dict[int, Dict] = None,
        ppi: float = 96.0,
        default_height_mm: float = 5.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        """
        Detects ArUco tokens in the frame and applies parallax correction.
        Resolves duplicate IDs by selecting the one with the largest area.
        """
        if self.camera_matrix is None or self.R is None:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)

        if ids is None:
            return []

        # 1. Group detections by ID and calculate areas
        detections_by_id = {}
        for i, marker_id_arr in enumerate(ids):
            marker_id = int(marker_id_arr[0])
            marker_corners = corners[i][0]

            # Area of the marker in camera pixels
            area = cv2.contourArea(marker_corners)

            if marker_id not in detections_by_id:
                detections_by_id[marker_id] = []

            detections_by_id[marker_id].append(
                {"corners": marker_corners, "area": area}
            )

        tokens = []
        ppi_mm = ppi / 25.4

        for marker_id, detections in detections_by_id.items():
            # Sort by area descending
            sorted_detections = sorted(
                detections, key=lambda x: x["area"], reverse=True
            )

            for i, det in enumerate(sorted_detections):
                marker_corners = det["corners"]
                u, v = np.mean(marker_corners, axis=0)

                # Apply parallax correction
                height_mm = default_height_mm
                if token_configs and marker_id in token_configs:
                    height_mm = token_configs[marker_id].get(
                        "height_mm", default_height_mm
                    )

                wx_mm, wy_mm = self._parallax_correction(u, v, height_mm)

                # Map to projector pixels
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
                        confidence=1.0,
                        is_duplicate=(i > 0),
                    )
                )

        return tokens

    def _parallax_correction(self, u: float, v: float, h: float) -> Tuple[float, float]:
        """
        Intersects the ray from camera through (u, v) with the plane z = h.
        Returns (X, Y) in world space.
        """
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
            return 0.0, 0.0  # Should not happen if camera is above table

        s = (h - cz) / vz
        p_world = self.camera_center_world + s * v_world

        return p_world[0], p_world[1]
