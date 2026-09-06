"""
Module for the sequential stereo calibration solver.
"""

import cv2
import numpy as np

from .token_manager import TokenManager


class SequentialSolver:
    def __init__(
        self,
        token_manager: TokenManager,
        projector_ppi: float,
        projector_matrix: np.ndarray,
        pattern_params: dict,
    ):
        self.token_manager = token_manager
        self.projector_ppi = projector_ppi
        self.projector_matrix = projector_matrix
        self.pattern_params = pattern_params
        self.camera_left_extrinsics = None
        self.camera_right_extrinsics = None
        self.r_stereo = None
        self.t_stereo = None
        self.grid_corners_3d = []

        # Intrinsics (will be set by the Wizard)
        self.k_left = None
        self.dist_left = None
        self.k_right = None
        self.dist_right = None

    def solve_phase1_table_scale(
        self,
        left_markers: list[tuple[int, np.ndarray]],
        right_markers: list[tuple[int, np.ndarray]],
        ruler_distance_mm: float = 100.0,
    ) -> float:
        """
        Phase 1: Table Scale & Z=0 Homography.
        Calculates projector_ppi and maps projected grid to physical tabletop coordinates.
        """
        ppi_values = []

        # 1. Calculate PPI from Ruler (IDs 40 & 41)
        # We check both left and right ruler detections for robustness
        for markers in [left_markers, right_markers]:
            m40 = next((corners for id, corners in markers if id == 40), None)
            m41 = next((corners for id, corners in markers if id == 41), None)

            if m40 is not None and m41 is not None:
                dist_px = np.linalg.norm(np.mean(m40, axis=0) - np.mean(m41, axis=0))
                dist_inches = ruler_distance_mm / 25.4
                ppi_values.append(dist_px / dist_inches)

        # 2. Calculate PPI from Grid (IDs 42-47)
        found_grid_ppi = False

        # Combine all detections for grid ID lookup
        all_markers = left_markers + right_markers
        grid_map = {
            id: corners for id, corners in all_markers if id in [42, 43, 44, 45, 46, 47, 48, 49]
        }

        # Check for horizontal pairs (e.g., 42-43, 44-45, 46-47)
        for i in range(3):
            id1, id2 = 42 + 2 * i, 43 + 2 * i
            if id1 in grid_map and id2 in grid_map:
                dist_px = np.linalg.norm(
                    np.mean(grid_map[id1], axis=0) - np.mean(grid_map[id2], axis=0)
                )
                ppi_values.append(dist_px / (40.0 / 25.4))
                found_grid_ppi = True
                break

        if not found_grid_ppi:
            # Check vertical pairs (e.g., 42-45, 43-46, 44-47)
            for i in range(4):
                id1, id2 = 42 + i, 46 + i
                if id1 in grid_map and id2 in grid_map:
                    dist_px = np.linalg.norm(
                        np.mean(grid_map[id1], axis=0) - np.mean(grid_map[id2], axis=0)
                    )
                    ppi_values.append(dist_px / (40.0 / 25.4))
                    break

        if not ppi_values:
            raise ValueError("Could not determine PPI from ruler or grid markers.")

        self.projector_ppi = float(np.mean(ppi_values))

        # Ruler center as (0, 0, 0)
        # We use the midpoint of 40 and 41 from the first ruler that has both markers.
        # This midpoint becomes the (0, 0, 0) origin of our world coordinate system.
        m40_origin = None
        m41_origin = None

        for markers in [left_markers, right_markers]:
            m40 = next((corners for id, corners in markers if id == 40), None)
            m41 = next((corners for id, corners in markers if id == 41), None)
            if m40 is not None and m41 is not None:
                m40_origin = m40
                m41_origin = m41
                break

        if m40_origin is None or m41_origin is None:
            raise ValueError("Could not find ruler markers in either camera.")

        # The grid markers (IDs 42-49) are at (ox, oy) relative to this origin.
        # Grid layout for 8 markers (2x4):
        # Row 0: 42, 43, 44, 45 (oy=-20)
        # Row 1: 46, 47, 48, 49 (oy=20)
        # ox = (j - 1.5) * 40
        # oy = (i - 0.5) * 40
        # The loop order (i=0..1, j=0..3) matches the ID order 42-49.
        # (Note: y-axis points down in OpenCV)
        # This layout ensures row 0 is above row 1.

        self.grid_corners_3d = []
        for i in range(2):
            for j in range(4):
                ox_mm = (j - 1.5) * 40
                oy_mm = (i - 0.5) * 40
                self.grid_corners_3d.append(np.array([ox_mm, oy_mm, 0.0], dtype=np.float32))

        return self.projector_ppi

    def solve_phase2_stereo_extrinsics(
        self,
        left_marker_corners: list[np.ndarray],
        right_marker_corners: list[np.ndarray],
        token_heights: dict[str, float],
    ) -> None:
        """
        Phase 2: Joint Non-Planar Stereo Extrinsics Solve.
        Uses token points (Z=h) and table points (Z=0) to solve extrinsics.
        """
        # Token 3D positions (relative to ruler center)
        # Token 0: (-60, 20), Token 1: (60, 20), Token 2: (-60, -20), Token 3: (60, -20)
        # Z coordinate is the height of the token.
        token_3d_positions = []
        positions = [(-60, 20), (60, 20), (-60, -20), (60, -20)]
        for i in range(4):
            tid = str(i)
            h = token_heights.get(tid, 50.0)
            ox, oy = positions[i]
            token_3d_positions.append(np.array([ox, oy, h], dtype=np.float32))

        # Combine grid corners and token positions
        all_points_3d = np.array(self.grid_corners_3d, dtype=np.float32)
        for i in range(4):
            all_points_3d = np.vstack([all_points_3d, token_3d_positions[i]])

        # left_marker_corners and right_marker_corners must have the same length as all_points_3d (12)
        if len(left_marker_corners) != 12 or len(right_marker_corners) != 12:
            raise ValueError(
                f"Expected 12 markers (8 grid + 4 tokens), but found {len(left_marker_corners)} left and {len(right_marker_corners)} right."
            )

        pts_l = np.array([m for m in left_marker_corners], dtype=np.float32)
        np.array([m for m in right_marker_corners], dtype=np.float32)

        # Solve PnP for left camera
        success_l, r_l, t_l = cv2.solvePnP(all_points_3d, pts_l, self.k_left, self.dist_left)
        if not success_l:
            raise RuntimeError("Failed to solve PnP for left camera")
        self.camera_left_extrinsics = cv2.Rodrigues(r_l)[0]
        self.camera_left_t = t_l

        # Compute 3D points relative to left camera
        # pts_r_raw is already in camera right frame.
        # cv2.stereoCalibrate will find R, t such that P_cam_r = R * P_cam_l + t.
        pts_r_raw = np.array([m for m in right_marker_corners])

        # Solve for relative transform using stereoCalibrate
        # We use CALIB_FIX_INTRINSIC since we already have k and dist
        r_stereo, t_stereo, _, _, _, _ = cv2.stereoCalibrate(
            all_points_3d,
            pts_l,
            pts_r_raw,
            self.k_left,
            self.dist_left,
            self.k_right,
            self.dist_right,
            cv2.CALIB_FIX_INTRINSIC,
        )

        self.r_stereo = r_stereo
        self.t_stereo = t_stereo

        # Now compute absolute extrinsics for right camera
        # R_r = R_stereo * R_l
        # t_r = T_stereo + R_stereo * t_l
        self.camera_right_extrinsics = self.r_stereo @ self.camera_left_extrinsics
        self.camera_right_t = (
            self.r_stereo @ self.camera_left_t.reshape(3, 1)
        ).flatten() + self.t_stereo

    def solve_phase3_auto_discovery(self) -> tuple[str, str]:
        """
        Phase 3: Auto-Discovery & Orientation Verification.
        Computes R_stereo, T_stereo and assigns camera roles.
        """
        if self.r_stereo is None or self.t_stereo is None:
            raise ValueError("Extrinsics not solved yet.")

        tx = self.t_stereo[0]

        # Verify rotation angle < 10 degrees
        trace_r = np.trace(self.r_stereo)
        cos_theta = np.clip((trace_r - 1) / 2.0, -1.0, 1.0)
        theta = np.arccos(cos_theta)

        if theta > np.deg2rad(10.0):
            raise RuntimeError(f"Significant rotation detected: {np.rad2deg(theta):.2f} degrees")

        # Assignment
        # Camera observing positive +Tx horizontal displacement is right.
        if tx > 0:
            left_id = "camera_0"
            right_id = "camera_1"
        else:
            left_id = "camera_1"
            right_id = "camera_0"

        return left_id, right_id
