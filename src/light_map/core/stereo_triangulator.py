from dataclasses import dataclass

import cv2
import numpy as np

from light_map.core.common_types import DetectionResult, ResultType


@dataclass
class StereoTriangulationResult:
    world_x: float
    world_y: float
    world_z: float
    confidence: float
    is_occluded: bool
    source_type: str  # "stereo", "fallback_token", "fallback_hand"


class StereoTriangulator:
    """
    Aggregates 2D detections from dual cameras into 3D table-relative coordinates.
    Implements sliding nearest-neighbor matching and single-camera fallback.
    """

    def __init__(
        self,
        camera_left_intrinsics: np.ndarray,
        camera_left_dist: np.ndarray,
        camera_right_intrinsics: np.ndarray,
        camera_right_dist: np.ndarray,
        rotation_left: np.ndarray,  # R_L
        translation_left: np.ndarray,  # t_L
        rotation_right: np.ndarray,  # R_R
        translation_right: np.ndarray,  # t_R
        roi_left: list[int],
        roi_right: list[int],
        frame_time: float,
        max_allowed_skew: float = 0.1,
    ):
        self.K_L = camera_left_intrinsics
        self.dist_L = camera_left_dist
        self.K_R = camera_right_intrinsics
        self.dist_R = camera_right_dist

        self.R_L = rotation_left
        self.t_L = (
            translation_left.reshape(3, 1) if translation_left.ndim == 1 else translation_left
        )
        self.R_R = rotation_right
        self.t_R = (
            translation_right.reshape(3, 1) if translation_right.ndim == 1 else translation_right
        )

        self.roi_L = roi_left
        self.roi_R = roi_right
        self.frame_time = frame_time
        self.max_allowed_skew = max_allowed_skew

        self.delta_t_match = min(0.4 * frame_time, max_allowed_skew)

        self.z_last_known = 0.0

        # Buffers for matching
        self.left_buffer: list[DetectionResult] = []
        self.right_buffer: list[DetectionResult] = []

        # Precompute projection matrices
        # P_L = K_L * [R_L | t_L]
        # P_R = K_R * [R_R | t_R]
        self.P_L = self.K_L @ np.hstack((self.R_L, self.t_L))
        self.P_R = self.K_R @ np.hstack((self.R_R, self.t_R))

        # Precompute inverses for fallback
        self.K_L_inv = np.linalg.inv(self.K_L)

        # Token profiles for fallback (heights)
        # This should ideally come from a config, but for now we'll assume
        # the result object might carry its own height if it's a token.
        # We'll use the height from the Token object if it exists in the metadata.
        # Or we can use a default.

    @classmethod
    def from_calibration_dict(
        cls,
        data: dict,
        frame_time: float = 0.033,
        max_allowed_skew: float = 0.1,
    ) -> "StereoTriangulator":
        """Constructs StereoTriangulator from calibration dictionary."""

        def get_mat(k1, k2, default):
            v = data.get(k1, data.get(k2))
            return np.array(v, dtype=np.float32) if v is not None else default

        # Left intrinsics
        k_l_val = data.get("camera_left_intrinsics")
        if isinstance(k_l_val, dict) and "matrix" in k_l_val:
            K_L = np.array(k_l_val["matrix"], dtype=np.float32)
            dist_L = np.array(k_l_val.get("dist", np.zeros(5)), dtype=np.float32)
        else:
            K_L = get_mat("camera_left_intrinsics", "k_left", np.eye(3, dtype=np.float32))
            dist_L = get_mat("camera_left_dist", "dist_left", np.zeros(5, dtype=np.float32))

        # Right intrinsics
        k_r_val = data.get("camera_right_intrinsics")
        if isinstance(k_r_val, dict) and "matrix" in k_r_val:
            K_R = np.array(k_r_val["matrix"], dtype=np.float32)
            dist_R = np.array(k_r_val.get("dist", np.zeros(5)), dtype=np.float32)
        else:
            K_R = get_mat("camera_right_intrinsics", "k_right", np.eye(3, dtype=np.float32))
            dist_R = get_mat("camera_right_dist", "dist_right", np.zeros(5, dtype=np.float32))

        R_L = get_mat("r_world_to_l", "r_left", np.eye(3, dtype=np.float32))
        t_L = get_mat("t_world_to_l", "t_left", np.zeros((3, 1), dtype=np.float32))
        R_R = get_mat("r_world_to_r", "r_right", np.eye(3, dtype=np.float32))
        t_R = get_mat("t_world_to_r", "t_right", np.zeros((3, 1), dtype=np.float32))

        roi_l = list(data.get("roi_left", [0, 0, 1920, 1080]))
        roi_r = list(data.get("roi_right", [0, 0, 1920, 1080]))

        return cls(
            camera_left_intrinsics=K_L,
            camera_left_dist=dist_L,
            camera_right_intrinsics=K_R,
            camera_right_dist=dist_R,
            rotation_left=R_L,
            translation_left=t_L,
            rotation_right=R_R,
            translation_right=t_R,
            roi_left=roi_l,
            roi_right=roi_r,
            frame_time=frame_time,
            max_allowed_skew=max_allowed_skew,
        )

    @classmethod
    def from_calibration_file(
        cls,
        filepath: str,
        frame_time: float = 0.033,
        max_allowed_skew: float = 0.1,
    ) -> "StereoTriangulator":
        """Constructs StereoTriangulator directly from a JSON calibration file."""
        import json

        with open(filepath) as f:
            data = json.load(f)
        return cls.from_calibration_dict(
            data, frame_time=frame_time, max_allowed_skew=max_allowed_skew
        )

    def _undistort_point(self, u: float, v: float, K: np.ndarray, dist: np.ndarray) -> np.ndarray:
        pts = np.array([[u, v]], dtype=np.float32)
        pts_undist = cv2.undistortPoints(pts, K, dist, P=K)
        return pts_undist[0]

    def triangulate_corners(self, corners_L: np.ndarray, corners_R: np.ndarray) -> np.ndarray:
        """Triangulates 4 marker corner points in pixel coordinates to 3D world coordinates (mm)."""
        pts_L = np.asarray(corners_L, dtype=np.float32).reshape(-1, 2)
        pts_R = np.asarray(corners_R, dtype=np.float32).reshape(-1, 2)

        uL = pts_L[:, 0] + self.roi_L[0]
        vL = pts_L[:, 1] + self.roi_L[1]
        uR = pts_R[:, 0] + self.roi_R[0]
        vR = pts_R[:, 1] + self.roi_R[1]

        undist_L = cv2.undistortPoints(
            np.column_stack([uL, vL]).reshape(-1, 1, 2), self.K_L, self.dist_L, P=self.K_L
        ).reshape(-1, 2)
        undist_R = cv2.undistortPoints(
            np.column_stack([uR, vR]).reshape(-1, 1, 2), self.K_R, self.dist_R, P=self.K_R
        ).reshape(-1, 2)

        pts_4d = cv2.triangulatePoints(self.P_L, self.P_R, undist_L.T, undist_R.T)
        pts_3d = (pts_4d[:3] / pts_4d[3:]).T
        return pts_3d.astype(np.float32)

    def intersect_corners_ray_plane(self, corners_L: np.ndarray, h_token: float) -> np.ndarray:
        """Calculates 3D world points for corners using single-camera ray-plane intersection."""
        pts_L = np.asarray(corners_L, dtype=np.float32).reshape(-1, 2)
        uL = pts_L[:, 0] + self.roi_L[0]
        vL = pts_L[:, 1] + self.roi_L[1]

        undist_L = cv2.undistortPoints(
            np.column_stack([uL, vL]).reshape(-1, 1, 2), self.K_L, self.dist_L, P=self.K_L
        ).reshape(-1, 2)

        C_L = (-self.R_L.T @ self.t_L).flatten()
        homog = np.column_stack([undist_L, np.ones(len(undist_L), dtype=np.float32)])
        d_cam = (self.K_L_inv @ homog.T).T
        d_world = (self.R_L.T @ d_cam.T).T

        s = (h_token - C_L[2]) / (d_world[:, 2] + 1e-9)
        pts_3d = C_L.reshape(1, 3) + s.reshape(-1, 1) * d_world
        return pts_3d.astype(np.float32)

    def update_buffers(self, result: DetectionResult):
        """Add new detection to the appropriate buffer and prune old ones."""
        if result.camera_id == "left":
            self.left_buffer.append(result)
        elif result.camera_id == "right":
            self.right_buffer.append(result)

        # Prune buffer to keep only the last 3 frame periods
        # (Requirement says 2-3 frame periods)
        max_buffer_size = 3
        if len(self.left_buffer) > max_buffer_size:
            self.left_buffer = self.left_buffer[-max_buffer_size:]
        if len(self.right_buffer) > max_buffer_size:
            self.right_buffer = self.right_buffer[-max_buffer_size:]

    def process_left_result(self, left_res: DetectionResult) -> StereoTriangulationResult:
        """
        Matches a left result against the right buffer and triangulates.
        """
        best_right: DetectionResult | None = None
        min_diff = float("inf")

        # Nearest neighbor search
        for right_res in self.right_buffer:
            diff = abs(left_res.timestamp - right_res.timestamp)
            if diff < min_diff:
                min_diff = diff
                best_right = right_res

        # Check if best match is within threshold
        if best_right and min_diff <= self.delta_t_match:
            # Triangulate
            # 1. ROI Offset Addition
            uL = left_res.data["u"] + self.roi_L[0]
            vL = left_res.data["v"] + self.roi_L[1]
            uR = best_right.data["u"] + self.roi_R[0]
            vR = best_right.data["v"] + self.roi_R[1]

            # 2. Lens Undistortion
            pts_L_undist = self._undistort_point(uL, vL, self.K_L, self.dist_L)
            pts_R_undist = self._undistort_point(uR, vR, self.K_R, self.dist_R)

            # 3. Triangulation
            pts_L_2d = pts_L_undist.reshape(2, 1)
            pts_R_2d = pts_R_undist.reshape(2, 1)
            pts_4d = cv2.triangulatePoints(self.P_L, self.P_R, pts_L_2d, pts_R_2d)
            X = float(pts_4d[0, 0] / pts_4d[3, 0])
            Y = float(pts_4d[1, 0] / pts_4d[3, 0])
            Z_mm = float(pts_4d[2, 0] / pts_4d[3, 0])

            # 4. Reprojection Error Filtering
            # Project back to Left camera
            proj_L_hom = self.P_L @ np.array([X, Y, Z_mm, 1.0])
            proj_L = proj_L_hom[:2] / proj_L_hom[2]

            # Reprojection error
            err_L = np.linalg.norm(pts_L_undist.flatten() - proj_L)

            # Project back to Right camera
            proj_R_hom = self.P_R @ np.array([X, Y, Z_mm, 1.0])
            proj_R = proj_R_hom[:2] / proj_R_hom[2]

            # Reprojection error
            err_R = np.linalg.norm(pts_R_undist.flatten() - proj_R)

            if err_L <= 3.0 and err_R <= 3.0:
                # Update z_last_known if it's a hand
                if left_res.type != ResultType.ARUCO:
                    self.z_last_known = float(Z_mm)

                return StereoTriangulationResult(
                    world_x=float(X),
                    world_y=float(Y),
                    world_z=float(Z_mm),
                    confidence=left_res.confidence,
                    is_occluded=False,
                    source_type="stereo",
                )

        # Fallback logic
        # We need to provide the undistorted points to the fallback handler
        # But we need to calculate them even if best_right was None
        uL_fallback = left_res.data["u"] + self.roi_L[0]
        vL_fallback = left_res.data["v"] + self.roi_L[1]
        pts_L_undist_fallback = self._undistort_point(
            uL_fallback, vL_fallback, self.K_L, self.dist_L
        )

        return self._handle_fallback(left_res, pts_L_undist_fallback)

    def _handle_fallback(
        self, left_res: DetectionResult, pts_L_undist: np.ndarray
    ) -> StereoTriangulationResult:
        """
        Single-camera fallback logic.
        """
        # Fallback logic depends on what we are tracking
        # If it's a token, we use h_token
        # If it's a hand, we use Z_last_known

        # For simplicity, we'll check the data to see if it's a token
        # This logic should be refined based on how DetectionResult is structured
        is_token = "token_id" in left_res.data or left_res.type == ResultType.ARUCO

        if is_token:
            # h_token from metadata or default
            h_token = left_res.data.get("h_token", 50.0)
            # Ray direction in camera space
            # pts_L_undist is [uL, vL]
            d_cam = self.K_L_inv @ np.concatenate([pts_L_undist.flatten(), [1.0]])

            # d_world = R_L^T * d_cam
            d_world = self.R_L.T @ d_cam

            # Intersect with Z = h_token
            # s = (h_token - C_L_z) / d_world_z
            # C_L is the camera center in world coords.
            # Since P_L = K_L * [R_L | t_L], the camera center is -R_L^T * t_L
            C_L = (-self.R_L.T @ self.t_L).flatten()
            s = float((h_token - C_L[2]) / d_world[2])
            P_table = (C_L + s * d_world).flatten()

            return StereoTriangulationResult(
                world_x=float(P_table[0]),
                world_y=float(P_table[1]),
                world_z=float(P_table[2]),
                confidence=left_res.confidence,
                is_occluded=True,
                source_type="fallback_token",
            )
        else:
            # Hand fallback
            # Z_last_known - we'd need to store this in the state or the triangulator
            # For now, use a default (e.g. 0.0 or a specific height)
            d_cam = self.K_L_inv @ np.concatenate([pts_L_undist.flatten(), [1.0]])
            d_world = self.R_L.T @ d_cam

            C_L = (-self.R_L.T @ self.t_L).flatten()
            s = float((self.z_last_known - C_L[2]) / d_world[2])
            P_table = (C_L + s * d_world).flatten()

            return StereoTriangulationResult(
                world_x=float(P_table[0]),
                world_y=float(P_table[1]),
                world_z=float(P_table[2]),
                confidence=left_res.confidence,
                is_occluded=True,
                source_type="fallback_hand",
            )
