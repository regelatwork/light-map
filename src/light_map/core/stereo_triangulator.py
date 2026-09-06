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
        self.t_L = translation_left
        self.R_R = rotation_right
        self.t_R = translation_right

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

    def _undistort_point(self, u: float, v: float, K: np.ndarray, dist: np.ndarray) -> np.ndarray:
        pts = np.array([[u, v]], dtype=np.float32)
        pts_undist = cv2.undistortPoints(pts, K, dist, P=K)
        return pts_undist[0]

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
            pts_4d = cv2.triangulatePoints(self.P_L, self.P_R, pts_L_undist, pts_R_undist)
            X = pts_4d[0] / pts_4d[3]
            Y = pts_4d[1] / pts_4d[3]
            Z_mm = pts_4d[2] / pts_4d[3]

            # 4. Reprojection Error Filtering
            # Project back to Left camera
            proj_L = self.P_L @ np.array([X, Y, Z_mm, 1.0])
            proj_L /= proj_L[3]

            # Reprojection error
            err_L = np.linalg.norm(pts_L_undist - proj_L[:2])

            # Project back to Right camera
            proj_R = self.P_R @ np.array([X, Y, Z_mm, 1.0])
            proj_R /= proj_R[3]

            # Reprojection error
            err_R = np.linalg.norm(pts_R_undist - proj_R[:2])

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
            C_L = -self.R_L.T @ self.t_L
            s = (h_token - C_L[2]) / d_world[2]
            P_table = C_L + s * d_world

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

            C_L = -self.R_L.T @ self.t_L
            s = (self.z_last_known - C_L[2]) / d_world[2]
            P_table = C_L + s * d_world

            return StereoTriangulationResult(
                world_x=float(P_table[0]),
                world_y=float(P_table[1]),
                world_z=float(P_table[2]),
                confidence=left_res.confidence,
                is_occluded=True,
                source_type="fallback_hand",
            )
