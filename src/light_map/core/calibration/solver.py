"""
Sequential solver for stereo calibration and auto-discovery.
"""

import logging

import cv2
import numpy as np

from light_map.core.calibration.models import CalibrationResult, LensIntrinsics, StereoExtrinsics
from light_map.core.calibration.utils import compute_roi_pass2, get_marker_partition


logger = logging.getLogger(__name__)


class SequentialSolver:
    """
    Implements a multi-phase solver for stereo calibration.
    """

    def __init__(self, K_L: np.ndarray, dist_L: np.ndarray, K_R: np.ndarray, dist_R: np.ndarray):
        self.K_L = K_L
        self.dist_L = dist_L
        self.K_R = K_R
        self.dist_R = dist_R
        self.marker_partition = get_marker_partition()

    def solve(
        self,
        projected_grid_detections: list[dict],
        ppi_ruler_detections: list[dict],
        token_detections: list[dict],
        tokens_json: dict,
    ) -> CalibrationResult:
        """
        Executes the sequential solver.
        """
        # Phase 1: Table Scale & Z=0 Homography
        projector_ppi, table_points_list, table_homography = self._solve_phase_1(
            projected_grid_detections, ppi_ruler_detections
        )

        # Build 3D points and 2D points for all markers
        pts_3d = {}
        # Markers 42-49 are in table_pts (Z=0)
        for i, pt in enumerate(table_points_list):
            pts_3d[42 + i] = pt

        # Markers 0-3 are at corners with heights from token_dets
        corner_ids = [42, 45, 46, 49]
        for i, tid in enumerate([0, 1, 2, 3]):
            corner_id = corner_ids[i]
            if corner_id in pts_3d:
                x, y, _ = pts_3d[corner_id]
                h = 50.0
                for d in token_detections:
                    if d.get("id") == tid:
                        h = d.get("height_mm", 50.0)
                        break
                pts_3d[tid] = np.array([x, y, h], dtype=np.float32)

        # Collect 2D points for all markers from both cameras
        pts_2d_l = {}
        pts_2d_r = {}
        all_dets = []
        for d in token_detections:
            all_dets.append(d)
        for d in projected_grid_detections:
            all_dets.append(d)

        for d in all_dets:
            mid = d.get("id")
            if mid is not None and mid in pts_3d:
                side = d.get("side", "left")
                if side == "left":
                    pts_2d_l[mid] = np.array(d["points"], dtype=np.float32)
                else:
                    pts_2d_r[mid] = np.array(d["points"], dtype=np.float32)

        # Phase 2: Joint Non-Planar Stereo Extrinsics Solve
        extrinsics = self._solve_phase_2(
            token_detections, projected_grid_detections, table_points_list, tokens_json
        )

        # Phase 3: Auto-Discovery & Orientation Verification
        R_stereo_raw = extrinsics["R"]
        T_stereo_raw = extrinsics["t"]

        # Verify rotation angle
        angle = np.arccos(
            np.clip(
                (R_stereo_raw[0, 0] + R_stereo_raw[1, 1] + R_stereo_raw[2, 2] - 3) / 3, -1.0, 1.0
            )
        )
        if angle > np.radians(10):
            logger.warning(
                "Large rotation angle detected between cameras: %f degrees", np.degrees(angle)
            )

        # Determine camera roles
        R_stereo = R_stereo_raw.copy()
        T_stereo = T_stereo_raw.copy()
        if T_stereo[0] < 0:
            logger.info("Negative Tx detected. Swapping camera roles.")
            R_stereo = R_stereo_raw.T
            T_stereo = -R_stereo @ T_stereo_raw

        # ROI Calculation
        roi_left, roi_right = self._calculate_rois(
            pts_3d, pts_2d_l, pts_2d_r, R_stereo, T_stereo, projector_ppi
        )

        return CalibrationResult(
            camera_left_intrinsics=LensIntrinsics(matrix=self.K_L, dist=self.dist_L),
            camera_right_intrinsics=LensIntrinsics(matrix=self.K_R, dist=self.dist_R),
            stereo_extrinsics=StereoExtrinsics(R=R_stereo, t=T_stereo),
            projector_ppi=projector_ppi,
            roi_left=roi_left,
            roi_right=roi_right,
            table_homography=table_homography,
            scale_factor=projector_ppi,
        )

    def _solve_phase_1(
        self,
        grid_dets: list[dict],
        ruler_dets: list[dict],
        projected_grid_detections: list[dict] = None,
    ) -> tuple[float, list[np.ndarray], np.ndarray]:
        """
        Phase 1: Calculate projector_ppi and map projected grid points to Z=0 tabletop coordinates,
        and compute the tabletop-to_left-camera homography.
        """
        p40_l = None
        p41_l = None

        if projected_grid_detections is None:
            projected_grid_detections = grid_dets

        for det in ruler_dets:
            side = det.get("side", "left")
            mid = det.get("id")
            if mid is None or side != "left":
                continue

            if mid == 40:
                p40_l = np.array(det["points"], dtype=np.float32)
            elif mid == 41:
                p41_l = np.array(det["points"], dtype=np.float32)

        if p40_l is None or p41_l is None:
            logger.error("Could not find markers 40 and 41 in left camera detections")
            return 96.0, [], np.eye(3)

        # Calculate PPI from ruler (distance between 40 and 41)
        p40_center = np.mean(p40_l, axis=0)
        p41_center = np.mean(p41_l, axis=0)
        dist_px = np.linalg.norm(p40_center - p41_center)
        ppi = dist_px / (100.0 / 25.4)

        # Build 3D points (Z=0) and 2D projected points
        table_points = []
        grid_pixel_points = []

        # Markers 42-49 are in a 2x4 grid.
        # We'll map them to their expected positions on the tabletop.
        # Use projected_grid_detections as they are the ones we want to map.
        # The IDs are 42-49.

        # Layout (Row 0: 42, 43, 44, 45; Row 1: 46, 47, 48, 49)
        # A 2x4 grid:
        # (0,0) (1,0) (2,0) (3,0)
        # (0,1) (1,1) (2,1) (3,1)
        # IDs: 42, 43, 44, 45, 46, 47, 48, 49

        for det in projected_grid_detections:
            mid = det.get("id")
            if mid is None or mid < 42 or mid > 49:
                continue
            if mid == 40:
                # This block should not be reached because of mid < 42 or mid > 49
                pass
            elif mid == 41:
                # This block should not be reached because of mid < 42 or mid > 49
                pass
            else:
                grid_idx = mid - 42
                ox = (grid_idx % 4 - 1.5) * 40
                oy = (grid_idx // 4 - 0.5) * 40
                table_points.append(np.array([ox, oy, 0.0], dtype=np.float32))
                grid_pixel_points.append(np.mean(det["points"], axis=0))

        table_points = np.array(table_points, dtype=np.float32)
        grid_pixel_points = np.array(grid_pixel_points, dtype=np.float32)

        # Compute homography from tabletop (Z=0) to left camera image
        # Ensure points are in (N, 1, 2) format for findHomography
        homography, _ = cv2.findHomography(
            np.array(table_points[:, :2], dtype=np.float32),
            np.array(grid_pixel_points, dtype=np.float32),
        )

        return ppi, table_points.tolist(), homography

    def _solve_phase_2(
        self,
        token_dets: list[dict],
        grid_dets: list[dict],
        table_pts_list: list[np.ndarray],
        tokens_json: dict,
    ) -> dict[str, np.ndarray]:
        """
        Phase 2: Solve for R and t using Z=0 points and Z=h points.
        """
        table_pts = np.array(table_pts_list)

        # Build a map of 3D points for all markers
        pts_3d = {}
        # Markers 42-49 are in table_pts (Z=0)
        for i, pt in enumerate(table_pts):
            pts_3d[42 + i] = pt

        # Markers 0-3 are at corners with heights from token_dets
        corner_ids = [42, 45, 46, 49]
        for i, tid in enumerate([0, 1, 2, 3]):
            corner_id = corner_ids[i]
            if corner_id in pts_3d:
                x, y, _ = pts_3d[corner_id]
                h = 50.0
                for d in token_dets:
                    if d.get("id") == tid:
                        h = d.get("height_mm", 50.0)
                        break
                pts_3d[tid] = np.array([x, y, h], dtype=np.float32)

        # Collect 2D points for all markers from both cameras
        pts_2d_l = {}
        pts_2d_r = {}
        all_dets = []
        for d in token_dets:
            all_dets.append(d)
        for d in grid_dets:
            all_dets.append(d)

        for d in all_dets:
            mid = d.get("id")
            if mid is not None and mid in pts_3d:
                side = d.get("side", "left")
                if side == "left":
                    pts_2d_l[mid] = np.array(d["points"], dtype=np.float32)
                else:
                    pts_2d_r[mid] = np.array(d["points"], dtype=np.float32)

        # Prepare points for cv2.stereoCalibrate
        common_ids = sorted([mid for mid in pts_3d if mid in pts_2d_l and mid in pts_2d_r])
        pts_l = np.vstack([pts_2d_l[mid].reshape(-1, 2) for mid in common_ids]).astype(np.float32)
        pts_r = np.vstack([pts_2d_r[mid].reshape(-1, 2) for mid in common_ids]).astype(np.float32)
        pts_3d_common = np.vstack([pts_3d[mid] for mid in common_ids]).astype(np.float32)

        pts_l = pts_l.reshape(len(common_ids), 2)
        pts_r = pts_r.reshape(len(common_ids), 2)
        pts_3d_common = pts_3d_common.reshape(len(common_ids), 3)

        logger.error(
            "Final shapes - pts_l: %s, pts_r: %s, pts_3d_common: %s",
            pts_l.shape,
            pts_r.shape,
            pts_3d_common.shape,
        )
        logger.error("pts_3d_common values: %s", pts_3d_common)
        logger.error("pts_l values: %s", pts_l)
        logger.error("pts_r values: %s", pts_r)

        if len(pts_l) < 4:
            logger.warning("Not enough points for stereo calibration: %d points", len(pts_l))
            return {"R": np.eye(3), "t": np.array([0.128, 0, 0], dtype=np.float32)}

        # Use cv2.stereoCalibrate
        ret = cv2.stereoCalibrate(
            [pts_3d_common],
            [pts_l],
            [pts_r],
            self.K_L,
            self.dist_L,
            self.K_R,
            self.dist_R,
            (1920, 1080),
            flags=cv2.CALIB_FIX_INTRINSIC,
        )
        r_stereo, t_stereo = ret[5], ret[6]

        return {"R": r_stereo, "t": t_stereo}

    def _calculate_rois(
        self,
        pts_3d: dict[int, np.ndarray],
        pts_2d_l: dict[int, np.ndarray],
        pts_2d_r: dict[int, np.ndarray],
        r_stereo: np.ndarray,
        t_stereo: np.ndarray,
        projector_ppi: float,
    ) -> tuple[tuple, tuple]:
        """
        Phase 3 / Two-pass ROI calculation.
        """
        # 1. Find the pose of camera L relative to the tabletop.
        # We can use solvePnP with pts_3d and pts_2d_l.
        obj_pts = []
        img_pts = []
        for mid in pts_2d_l:
            if mid in pts_3d:
                obj_pts.append(pts_3d[mid])
                img_pts.append(pts_2d_l[mid])

        obj_pts = np.array(obj_pts, dtype=np.float32)
        img_pts = np.array(img_pts, dtype=np.float32)

        success, r_world_to_l, t_world_to_l = cv2.solvePnP(obj_pts, img_pts, self.K_L, None)
        if not success:
            logger.error("Failed to solvePnP for camera L pose.")
            return (0, 0, 1920, 1080), (0, 0, 1920, 1080)

        # 2. Project all points to both cameras.
        # pts_3d contains the 3D points in world coordinates.
        all_3d_pts = np.array(list(pts_3d.values())).reshape(-1, 3, 1).astype(np.float32)

        # Project to Camera L
        img_pts_l, _ = cv2.projectPoints(
            all_3d_pts, r_world_to_l, t_world_to_l, self.K_L, self.dist_L
        )
        img_pts_l = img_pts_l.reshape(-1, 2)

        # Project to Camera R
        # P_R_cam = R_stereo @ P_L_cam + t_stereo
        # P_L_cam = R_world_to_l @ P_world + t_world_to_l
        # P_R_cam = R_stereo @ (R_world_to_l @ P_world + t_world_to_l) + t_stereo
        # P_R_cam = (R_stereo @ R_world_to_l) @ P_world + (R_stereo @ t_world_to_l + t_stereo)
        # Since we are projecting from world to R directly using r_r and t_r:
        r_world_to_r = r_stereo @ r_world_to_l
        t_world_to_r = r_stereo @ t_world_to_l + t_stereo

        img_pts_r, _ = cv2.projectPoints(
            all_3d_pts, r_world_to_r, t_world_to_r, self.K_R, self.dist_R
        )
        img_pts_r = img_pts_r.reshape(-1, 2)

        # 3. Find bounding box and add margin.
        # We use the helper function for consistency.
        return compute_roi_pass2(
            sensor_res=(1920, 1080),
            r_l=r_world_to_l,
            t_l=t_world_to_l,
            r_r=r_world_to_r,
            t_r=t_world_to_r,
            projector_ppi=projector_ppi,
            pts_3d=all_3d_pts.reshape(-1, 3),
            k_l=self.K_L,
            dist_l=self.dist_L,
            k_r=self.K_R,
            dist_r=self.dist_R,
        )
