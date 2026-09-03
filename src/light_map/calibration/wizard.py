import logging
import json
import os
import numpy as np
import cv2
import time
from typing import Optional, Dict, Tuple, List

from light_map.vision.infrastructure.camera import Camera
from light_map.calibration.calibration_logic import (
    calculate_ppi_from_frame,
    calibrate_extrinsics,
    compute_projector_homography
)
from light_map.rendering.projector import generate_calibration_pattern

logger = logging.getLogger(__name__)

class StereoCalibrationWizard:
    def __init__(self, tokens_path: str = "tokens.json"):
        self.tokens_path = tokens_path
        self.token_data = self._load_tokens()
        self.projector_matrix = None
        self.camera_left_intrinsics = None
        self.camera_right_intrinsics = None
        self.camera_left_dist = None
        self.camera_right_dist = None
        self.ppi = None
        self.roi_left = None
        self.roi_right = None
        self.camera_left_id = None
        self.camera_right_id = None
        self.grid_corners_world = None

    def _load_tokens(self) -> Dict:
        if not os.path.exists(self.tokens_path):
            logger.warning(f"Tokens file {self.tokens_path} not found.")
            return {"token_profiles": {}}
        with open(self.tokens_path, "r") as f:
            return json.load(f)

    def get_valid_tokens(self) -> Dict[int, float]:
        """
        Filters tokens from tokens.json to only those with positive heights.
        """
        valid_tokens = {}
        profiles = self.token_data.get("token_profiles", {})
        defaults = self.token_data.get("aruco_defaults", {})

        for token_id, data in defaults.items():
            token_id = int(token_id)
            profile_name = data.get("profile")
            if profile_name in profiles:
                height = profiles[profile_name].get("height_mm", 0.0)
                if height > 0:
                    valid_tokens[token_id] = height
        return valid_tokens

    def resolve_lens_intrinsics(self, left_id: str, right_id: str):
        """
        Resolves intrinsics with fallback order:
        Camera Left: camera_left_calibration.npz -> camera_calibration.npz
        Camera Right: camera_right_calibration.npz -> camera_calibration.npz
        """
        def _load_npz(prefix: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
            paths = [f"{prefix}_calibration.npz", "camera_calibration.npz"]
            for path in paths:
                if os.path.exists(path):
                    data = np.load(path, allow_pickle=True)
                    return data.get("K"), data.get("dist")
            return None

        self.camera_left_intrinsics, self.camera_left_dist = _load_npz("camera_left")
        self.camera_right_intrinsics, self.camera_right_dist = _load_npz("camera_right")

        if self.camera_left_intrinsics is None or self.camera_right_intrinsics is None:
            logger.warning("Could not resolve lens intrinsics for one or both cameras.")

    def _detect_markers(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Detects ArUco markers in the given frame.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        return detector.detectMarkers(gray)

    def _discover_cameras(self, r_left: np.ndarray, t_left: np.ndarray, 
                           r_right: np.ndarray, t_right: np.ndarray,
                           cam_left: Camera, cam_right: Camera) -> tuple[str, str]:
        """
        Identifies Left vs Right camera based on translation vector and rotation.
        """
        tx = t_left[0]
        
        # Verify rotation alignment: R_left * R_right^T should be close to identity
        r_left_mat, _ = cv2.Rodrigues(r_left)
        r_right_mat, _ = cv2.Rodrigues(r_right)
        r_stereo = r_left_mat @ r_right_mat.T
        
        # Check if rotation is small (e.g., < 10 degrees)
        deviation = np.max(np.abs(r_stereo - np.eye(3)))
        if deviation > 0.1:
            logger.warning(f"Warning: Significant rotation detected between cameras (deviation: {deviation:.3f})")

        # Rule: Camera observing positive +Tx horizontal displacement is assigned camera_right.
        if tx > 0:
            # camera_left is at +X, so it's the right one.
            # So the left one is camera_right.
            return cam_right.id, cam_left.id
        else:
            # camera_left is at -X (or 0), so it's the left one.
            # So the right one is camera_right.
            return cam_left.id, cam_right.id

    def _get_ground_points(self, frame: np.ndarray, homography: np.ndarray, ppi: float, 
                            corners: np.ndarray, ids: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Phase 1: Table Scale & Z=0 Homography.
        Detects projected grid (IDs 42-47) and physical PPI sheet (IDs 40 & 41, d=100mm) simultaneously.
        Calculates physical PPI and maps projected marker corners to physical millimeter tabletop coordinates (X, Y, Z=0).
        """
        ids_flat = ids.flatten()
        
        # Find corners for 40 and 41
        idx40 = np.where(ids_flat == 40)[0][0]
        idx41 = np.where(ids_flat == 41)[0][0]
        
        # Get centers of 40 and 41 in camera space
        c40 = np.mean(corners[idx40][0], axis=0)
        c41 = np.mean(corners[idx41][0], axis=0)
        
        # Project to tabletop space using homography
        pts_cam = np.array([c40, c41]).reshape(-1, 1, 2).astype(np.float32)
        pts_table = cv2.perspectiveTransform(pts_cam, homography)
        
        # The distance between 40 and 41 in tabletop space should be 100mm
        dist_table = np.linalg.norm(pts_table[0][0] - pts_table[1][0])
        
        # Grid corners (IDs 42-47)
        grid_ids = [42, 43, 44, 45, 46, 47]
        grid_corners_cam = []
        grid_corners_world = []
        
        for gid in grid_ids:
            if gid in ids_flat:
                idx = np.where(ids_flat == gid)[0][0]
                c = np.mean(corners[idx][0], axis=0)
                c_cam = np.array(c).reshape(1, 1, 2).astype(np.float32)
                c_table = cv2.perspectiveTransform(c_cam, homography)[0][0]
                grid_corners_cam.append(c)
                grid_corners_world.append(c_table)
        
        # If we have at least some grid corners, return them
        if len(grid_corners_world) > 0:
            grid_corners_world = np.array(grid_corners_world, dtype=np.float32)
            grid_corners_cam = np.array(grid_corners_cam, dtype=np.float32)
            return grid_corners_cam, grid_corners_cam, grid_corners_world
        
        return None, None, None

    def _find_checkerboard_corners(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Detects checkerboard corners in the frame.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        corners, ids, _ = detector.detectMarkers(gray)
        
        if ids is not None:
            ids_flat = ids.flatten()
            grid_ids = [42, 43, 44, 45, 46, 47]
            grid_corners = []
            for gid in grid_ids:
                if gid in ids_flat:
                    idx = np.where(ids_flat == gid)[0][0]
                    grid_corners.append(corners[idx][0])
            if len(grid_corners) > 0:
                return np.array(grid_corners)
        return None

    def _compute_roi(self, frame_l: np.ndarray, r_left: np.ndarray, t_left: np.ndarray, 
                      r_right: np.ndarray, t_right: np.ndarray, 
                      k_left: np.ndarray, k_right: np.ndarray, 
                      dist_left: np.ndarray, dist_right: np.ndarray, 
                      ppi: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the sensor ROIs with 200mm parallax margin using a Two-Pass approach.
        """
        # --- Pass 1: Uncalibrated Bounds ---
        uncalibrated_corners = self._find_checkerboard_corners(frame_l)
        if uncalibrated_corners is not None:
            pts = uncalibrated_corners.reshape(-1, 2)
            min_x, min_y = np.min(pts, axis=0)
            max_x, max_y = np.max(pts, axis=0)
        else:
            logger.warning("Pass 1: Could not detect checkerboard corners for uncalibrated bounds.")
            min_x, min_y, max_x, max_y = 0, 0, 1920, 1080

        # --- Pass 2: 3D Parallax Volume Envelope ---
        if self.grid_corners_world is None:
            logger.warning("grid_corners_world is None, returning default ROI")
            return np.array([0, 0, 1920, 1080]), np.array([0, 0, 1920, 1080])

        grid_corners_0 = self.grid_corners_world.copy()
        grid_corners_200 = self.grid_corners_world.copy()
        grid_corners_200[:, 2] += 200.0

        points_to_project = np.vstack([grid_corners_0, grid_corners_200]) # (8, 3)

        # Project for left camera
        pts_l, _ = cv2.projectPoints(points_to_project, r_left, t_left, k_left, dist_left)
        pts_l = pts_l.reshape(-1, 2)

        # Project for right camera
        pts_r, _ = cv2.projectPoints(points_to_project, r_right, t_right, k_right, dist_right)
        pts_r = pts_r.reshape(-1, 2)

        def get_roi_with_margin(pts, img_size=(1920, 1080)):
            min_x = np.min(pts[:, 0])
            max_x = np.max(pts[:, 0])
            min_y = np.min(pts[:, 1])
            max_y = np.max(pts[:, 1])

            width = max_x - min_x
            height = max_y - min_y

            margin_x = width * 0.05
            margin_y = height * 0.05

            roi = np.array([
                min_x - margin_x,
                min_y - margin_y,
                max_x + margin_x,
                max_y + margin_y
            ])

            roi[0] = max(0, min(roi[0], img_size[0]))
            roi[1] = max(0, min(roi[1], img_size[1]))
            roi[2] = max(0, min(roi[2], img_size[0]))
            roi[3] = max(0, min(roi[3], img_size[1]))

            return roi

        roi_l = get_roi_with_margin(pts_l)
        roi_r = get_roi_with_margin(pts_r)

        return roi_l, roi_r

    def save_calibration(self, r_left, t_left, r_right, t_right, filepath: str = "stereo_calibration.json"):
        """
        Saves the calibration results to a JSON file.
        """
        data = {
            "camera_left_id": self.camera_left_id,
            "camera_right_id": self.camera_right_id,
            "roi_left": self.roi_left.tolist(),
            "roi_right": self.roi_right.tolist(),
            "ppi": self.ppi,
            "projector_matrix": self.projector_matrix.tolist(),
            "camera_left_intrinsics": self.camera_left_intrinsics.tolist(),
            "camera_left_dist": self.camera_left_dist.tolist(),
            "camera_right_intrinsics": self.camera_right_intrinsics.tolist(),
            "camera_right_dist": self.camera_right_dist.tolist(),
            "r_left": r_left.tolist(),
            "t_left": t_left.tolist(),
            "r_right": r_right.tolist(),
            "t_right": t_right.tolist(),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        logger.info(f"Calibration saved to {filepath}")

    def run_calibration(self, camera_left: Camera, camera_right: Camera) -> Dict:
        """
        Executes the unified stereo calibration procedure.
        """
        self.camera_left = camera_left
        self.camera_right = camera_right

        # Resolve Intrinsics
        self.resolve_lens_intrinsics(camera_left.id, camera_right.id)

        # Phase 1: Table Scale & Z=0 Homography
        logging.info("Phase 1: Detecting PPI markers (IDs 40, 41)...")

        best_homography = None
        best_ppi = None
        ground_points_cam = None
        ground_points_proj = None

        pattern_params = {"square_size": 100, "rows": 13, "cols": 18, "start_x": 100, "start_y": 100}

        for _ in range(100):
            frame_l = camera_left.read()
            frame_r = camera_right.read()

            if frame_l is None or frame_r is None:
                continue

            corners_l, ids_l, _ = self._detect_markers(frame_l)
            corners_r, ids_r, _ = self._detect_markers(frame_r)

            if ids_l is not None and 40 in ids_l.flatten() and 41 in ids_l.flatten():
                best_homography = compute_projector_homography(
                    frame_l,
                    pattern_params,
                    self.camera_left_intrinsics, self.camera_left_dist,
                    aruco_corners=corners_l, aruco_ids=ids_l
                )

                best_ppi = calculate_ppi_from_frame(
                    frame_l, best_homography,
                    aruco_corners=corners_l, aruco_ids=ids_l
                )

                ground_points_cam, grid_corners_proj, grid_corners_world = self._get_ground_points(
                    frame_l, best_homography, best_ppi, corners_l, ids_l
                )
                break

            time.sleep(0.1)

        if not best_homography or not best_ppi:
            raise RuntimeError("Failed to complete Phase 1: Markers 40/41 not detected.")

        self.projector_matrix = best_homography
        self.ppi = best_ppi
        self.grid_corners_world = grid_corners_world

        # Phase 2: Joint Non-Planar Stereo Extrinsics
        logging.info("Phase 2: Solving stereo extrinsics...")
        valid_tokens = self.get_valid_tokens()

        r_l, t_l, r_r, t_r, _ = calibrate_extrinsics(
            frame_l,
            self.projector_matrix,
            self.camera_left_intrinsics, self.camera_left_dist,
            valid_tokens,
            self.ppi,
            ground_points_cam=ground_points_cam,
            ground_points_proj=grid_corners_proj,
            token_sizes={k: 1 for k in valid_tokens.keys()}
        )

        if r_l is None:
            raise RuntimeError("Failed to solve stereo extrinsics.")

        # Phase 3: Auto-Discovery
        logging.info("Phase 3: Auto-discovering camera roles...")
        left_id_name, right_id_name = self._discover_cameras(r_l, t_l, r_r, t_r, camera_left, camera_right)
        self.camera_left_id = left_id_name
        self.camera_right_id = right_id_name

        # Phase 4: Two-Pass ROI Calculation
        logging.info("Phase 4: Computing ROIs...")
        self.roi_left, self.roi_right = self._compute_roi(
            frame_l, r_l, t_l, r_r, t_r,
            self.camera_left_intrinsics, self.camera_right_intrinsics,
            self.camera_left_dist, self.camera_right_dist,
            self.ppi
        )

        logging.info(f"Calibration complete. Left: {self.camera_left_id}, Right: {self.camera_right_id}")
        self.save_calibration(r_l, t_l, r_r, t_r)
        return {"status": "success", "left": self.camera_left_id, "right": self.camera_right_id}
