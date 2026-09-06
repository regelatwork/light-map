import logging

import cv2
import numpy as np

from ..core.config_schema import CalibrationConfig


class SequentialStereoSolver:
    def __init__(
        self,
        config: CalibrationConfig,
        camera_left_intrinsics: tuple[np.ndarray, np.ndarray],
        camera_right_intrinsics: tuple[np.ndarray, np.ndarray],
    ):
        self.config = config
        self.camera_left_intrinsics = camera_left_intrinsics
        self.camera_right_intrinsics = camera_right_intrinsics
        self.ppi = None
        self.homography = None
        self.grid_corners_world = None
        self.pattern_params = {
            "square_size": 100,
            "rows": 13,
            "cols": 18,
            "start_x": 100,
            "start_y": 100,
        }

    def solve(
        self,
        frame_l: np.ndarray,
        frame_r: np.ndarray,
        camera_matrix_l: np.ndarray,
        distortion_coefficients_l: np.ndarray,
        camera_matrix_r: np.ndarray,
        distortion_coefficients_r: np.ndarray,
        token_heights: dict[int, float],
        aruco_corners_l: tuple[np.ndarray, ...] | None,
        aruco_ids_l: np.ndarray | None,
        aruco_corners_r: tuple[np.ndarray, ...] | None,
        aruco_ids_r: np.ndarray | None,
        token_sizes: dict[int, int] | None,
    ) -> dict | None:
        """
        Executes the sequential solver phases.
        """

        # Phase 1: Table Scale & Z=0 Homography
        # Use IDs 40 and 41 to solve for camera-to-table transform and PPI.
        # We assume the PPI sheet is aligned with the table axes.
        transform, ppi = self.solve_phase_1(
            frame_l, aruco_corners_l, aruco_ids_l, camera_matrix_l, distortion_coefficients_l
        )

        if transform is None or ppi is None:
            logging.warning("Phase 1 failed: Could not solve transform or PPI.")
            return None

        self.ppi = ppi

        # Phase 2: Joint Non-Planar Stereo Extrinsics Solve
        # Use the transform from Phase 1 as an initial guess or to project points.
        # Actually, we'll use the points from both cameras.
        rvec_l, tvec_l, rvec_r, tvec_r, rms = self.solve_phase_2(
            frame_l,
            frame_r,
            camera_matrix_l,
            distortion_coefficients_l,
            camera_matrix_r,
            distortion_coefficients_r,
            token_heights,
            aruco_corners_l,
            aruco_ids_l,
            aruco_corners_r,
            aruco_ids_r,
            token_sizes,
        )

        if rvec_l is None:
            return None

        # Phase 3: Auto-Discovery & Orientation Verification
        roles = self.solve_phase_3(rvec_l, tvec_l, rvec_r, tvec_r)

        # Phase 4: Two-Pass ROI Calculation
        roi_l, roi_r = self.solve_phase_4(
            frame_l,
            rvec_l,
            tvec_l,
            rvec_r,
            tvec_r,
            camera_matrix_l,
            camera_matrix_r,
            distortion_coefficients_l,
            distortion_coefficients_r,
            self.ppi,
        )

        return {
            "rvec_l": rvec_l,
            "tvec_l": tvec_l,
            "rvec_r": rvec_r,
            "tvec_r": tvec_r,
            "rms": rms,
            "ppi": self.ppi,
            "roles": roles,
            "transform": transform,
            "roi_left": roi_l,
            "roi_right": roi_r,
        }

    def solve_phase_1(
        self,
        frame_l: np.ndarray,
        aruco_corners_l: tuple[np.ndarray, ...] | None,
        aruco_ids_l: np.ndarray | None,
        camera_matrix_l: np.ndarray,
        distortion_coefficients_l: np.ndarray,
    ) -> tuple[float, np.ndarray, np.ndarray] | None:
        from ..calibration.calibration_logic import (
            calculate_ppi_from_frame,
            compute_projector_homography,
        )

        corners_l, ids_l, _ = self._detect_markers(frame_l)

        if ids_l is not None and 40 in ids_l.flatten() and 41 in ids_l.flatten():
            self.homography = compute_projector_homography(
                frame_l,
                self.pattern_params,
                camera_matrix_l[0],
                camera_matrix_l[1],
                aruco_corners=corners_l,
                aruco_ids=ids_l,
            )

            self.ppi = calculate_ppi_from_frame(
                frame_l, self.homography, aruco_corners=corners_l, aruco_ids=ids_l
            )

            _, _, self.grid_corners_world = self._get_ground_points(
                frame_l, self.homography, self.ppi, corners_l, ids_l
            )

            return self.ppi, self.homography, self.grid_corners_world

        raise RuntimeError("Failed to complete Phase 1: Markers 40/41 not detected in frame.")

    def _detect_markers(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
        corners, ids, _ = detector.detectMarkers(gray)
        return corners, ids

    def _get_ground_points(
        self,
        frame: np.ndarray,
        homography: np.ndarray,
        ppi: float,
        corners: np.ndarray,
        ids: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        grid_corners_cam = []
        for g_id in range(42, 50):
            idx = np.where(ids.flatten() == g_id)[0]
            if len(idx) > 0:
                grid_corners_cam.append(corners[idx[0]][0])

        if len(grid_corners_cam) < 4:
            all_grid_corners = []
            for g_id in range(42, 50):
                idx = np.where(ids.flatten() == g_id)[0]
                if len(idx) > 0:
                    all_grid_corners.append(corners[idx[0]][0])

            if len(all_grid_corners) < 4:
                raise RuntimeError("Failed to detect enough grid markers (42-49).")

            all_grid_corners = np.array(all_grid_corners)
            min_y, max_y = np.min(all_grid_corners[:, 1]), np.max(all_grid_corners[:, 1])
            min_x, max_x = np.min(all_grid_corners[:, 0]), np.max(all_grid_corners[:, 0])
            grid_corners_cam = np.array(
                [[min_x, min_y], [max_x, min_y], [min_x, max_y], [max_x, max_y]]
            )

        grid_corners_proj = (homography @ grid_corners_cam.reshape(-1, 1, 2)).reshape(-1, 2)
        ppi_mm = ppi / 25.4
        world_points_proj = grid_corners_proj / ppi_mm
        world_points_3d = np.hstack([world_points_proj, np.zeros((4, 1))])

        return np.array(grid_corners_cam).reshape(4, 2), grid_corners_proj, world_points_3d

    def solve_phase_2(
        self,
        frame_l: np.ndarray,
        frame_r: np.ndarray,
        camera_matrix_l: np.ndarray,
        distortion_coefficients_l: np.ndarray,
        camera_matrix_r: np.ndarray,
        distortion_coefficients_r: np.ndarray,
        token_heights: dict[int, float],
        aruco_corners_l: tuple[np.ndarray, ...] | None,
        aruco_ids_l: np.ndarray | None,
        aruco_corners_r: tuple[np.ndarray, ...] | None,
        aruco_ids_r: np.ndarray | None,
        token_sizes: dict[int, int] | None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float] | None:
        from ..calibration.calibration_logic import solve_joint_extrinsics

        return solve_joint_extrinsics(
            frame_l,
            frame_r,
            self.projector_matrix,
            camera_matrix_l,
            distortion_coefficients_l,
            camera_matrix_r,
            distortion_coefficients_r,
            token_heights,
            self.ppi,
            aruco_corners_l,
            aruco_ids_l,
            aruco_corners_r,
            aruco_ids_r,
            token_sizes,
            None,  # grid_corners_l
            None,  # grid_corners_r
            self.grid_corners_world,
        )

    def solve_phase_3(
        self, r_l: np.ndarray, t_l: np.ndarray, r_r: np.ndarray, t_r: np.ndarray
    ) -> tuple[str, str]:
        """
        Discovers Left vs Right camera assignments based on T_x displacement.
        Verifies rotation alignment R_stereo.
        """
        # T_stereo is the translation from Left to Right.
        # If T_x > 0, then Right is to the right of Left.
        if t_l[0] > 0:
            left_id, right_id = "camera_left", "camera_right"
        else:
            left_id, right_id = "camera_right", "camera_left"

        # Verify rotation alignment
        # R_stereo should be close to identity
        rmat, _ = cv2.Rodrigues(r_l)
        trace = np.trace(rmat)
        angle_rad = np.arccos(np.clip((trace - 1) / 2, -1, 1))
        angle_deg = np.degrees(angle_rad)

        if angle_deg > 10.0:
            logging.warning(
                f"Rotation alignment verification failed: {angle_deg:.2f} degrees > 10.0 degrees."
            )

        return left_id, right_id

    def solve_phase_4(
        self,
        frame_l: np.ndarray,
        r_l: np.ndarray,
        t_l: np.ndarray,
        r_r: np.ndarray,
        t_r: np.ndarray,
        k_l: np.ndarray,
        k_r: np.ndarray,
        dist_l: np.ndarray,
        dist_r: np.ndarray,
        ppi: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Computes the sensor ROIs with 200mm parallax margin using a Two-Pass approach.
        """
        # --- Pass 1: Uncalibrated Bounds ---
        # This is a bit tricky because we need to detect grid corners in the raw frame.
        # We'll use the same logic as in wizard.py.
        # We need a way to detect checkerboard corners.
        # Let's assume the board size is (17, 12)
        board_size = (17, 12)
        gray = cv2.cvtColor(frame_l, cv2.COLOR_BGR2GRAY)
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

        ret, corners = detector.detectChessboardCorners(gray, board_size, None)
        if not ret:
            ret, corners = cv2.findChessboardCorners(gray, board_size, None)

        if not ret:
            logging.warning(
                "Pass 1: Could not detect checkerboard corners for uncalibrated bounds."
            )
            # Fallback to default ROI if detection fails
            return np.array([0, 0, 1920, 1080]), np.array([0, 0, 1920, 1080])

        pts = corners.reshape(-1, 2)
        min_x, min_y = np.min(pts, axis=0)
        max_x, max_y = np.max(pts, axis=0)

        # --- Pass 2: 3D Parallax Volume Envelope ---
        if self.grid_corners_world is None:
            return np.array([0, 0, 1920, 1080]), np.array([0, 0, 1920, 1080])

        grid_corners_0 = self.grid_corners_world.copy()
        grid_corners_200 = self.grid_corners_world.copy()
        grid_corners_200[:, 2] += 200.0

        points_to_project = np.vstack([grid_corners_0, grid_corners_200])  # (8, 3)

        pts_l, _ = cv2.projectPoints(points_to_project, r_l, t_l, k_l, dist_l)
        pts_l = pts_l.reshape(-1, 2)

        pts_r, _ = cv2.projectPoints(points_to_project, r_r, t_r, k_r, dist_r)
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

            roi = np.array([min_x - margin_x, min_y - margin_y, max_x + margin_x, max_y + margin_y])

            roi[0] = max(0, min(roi[0], img_size[0]))
            roi[1] = max(0, min(roi[1], img_size[1]))
            roi[2] = max(0, min(roi[2], img_size[0]))
            roi[3] = max(0, min(roi[3], img_size[1]))

            return roi

        roi_l = get_roi_with_margin(pts_l)
        roi_r = get_roi_with_margin(pts_r)

        return roi_l, roi_r
