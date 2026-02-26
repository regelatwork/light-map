import cv2
import numpy as np
import math
import random
import logging
from typing import List, Tuple, Optional, TYPE_CHECKING
from datetime import datetime

from light_map.common_types import Token
from light_map.map_system import MapSystem
from light_map.vision.debug_utils import DebugVisualizer

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel


class StructuredLightTokenDetector:
    # --- Structured Light Pattern Parameters ---
    SL_SEED = 42
    SL_DOT_RADIUS = 3
    SL_EDGE_MARGIN = SL_DOT_RADIUS * 4
    SL_SPACING_FACTOR = 0.5
    SL_MIN_SPACING = SL_DOT_RADIUS * 2 * 3
    SL_JITTER_FACTOR = 0.25

    # --- Structured Light Detection Parameters ---
    SL_MIN_DYNAMIC_THRESH = 40
    SL_DYNAMIC_THRESH_FACTOR = 0.75
    SL_MIN_GRAY_VAL = 30
    SL_MIN_CONTOUR_AREA = 2
    SL_SHIFT_THRESHOLD_PX = 15.0
    SL_MISSING_THRESHOLD_PX = 15.0

    # --- Clustering & Result Parameters ---
    CLUSTER_DIST_PX = 80.0
    CONFIDENCE_SCALING = 3.0

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvec = None
        self.tvec = None
        self.R = None
        self.camera_center_world = None

        # Performance optimization
        self._fov_mask = None
        self._fov_mask_params = None

    def set_calibration(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs

    def set_extrinsics(self, rvec: np.ndarray, tvec: np.ndarray):
        self.rvec = rvec
        self.tvec = tvec
        if self.rvec is not None and self.tvec is not None:
            self.R, _ = cv2.Rodrigues(self.rvec)
            self.camera_center_world = -self.R.T @ self.tvec.flatten()

    def get_scan_pattern(
        self, width: int, height: int, ppi: float
    ) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
        """
        Generates a jittered staggered (hexagonal) dot grid pattern for optimal coverage.
        Returns: (pattern_image, list_of_expected_points_projector_space)
        """
        img = np.zeros((height, width, 3), dtype=np.uint8)
        expected_points = []

        # Spacing to account for effective resolution
        spacing = max(self.SL_MIN_SPACING, int(ppi * self.SL_SPACING_FACTOR))

        # Vertical spacing for equilateral triangles (h = d * sin(60) = d * sqrt(3)/2)
        row_spacing = int(spacing * math.sqrt(3) / 2)

        # Constrain jitter to guarantee separation
        max_jitter = max(1, int(spacing * self.SL_JITTER_FACTOR))

        # Use local random instance for thread-safety and determinism
        rng = random.Random(self.SL_SEED)

        row_idx = 0
        for y in range(spacing // 2, height, row_spacing):
            # Stagger every other row
            x_offset = (spacing // 2) if (row_idx % 2 == 1) else 0

            for x in range(spacing // 2 + x_offset, width, spacing):
                jx = x + rng.randint(-max_jitter, max_jitter)
                jy = y + rng.randint(-max_jitter, max_jitter)

                # Ensure within bounds with margin to avoid straddling the border
                jx = max(self.SL_EDGE_MARGIN, min(width - 1 - self.SL_EDGE_MARGIN, jx))
                jy = max(self.SL_EDGE_MARGIN, min(height - 1 - self.SL_EDGE_MARGIN, jy))

                cv2.circle(img, (jx, jy), self.SL_DOT_RADIUS, (255, 255, 255), -1)
                expected_points.append((jx, jy))

            row_idx += 1

        return img, expected_points

    def detect(
        self,
        frame_pattern: np.ndarray,
        frame_dark: np.ndarray,
        expected_points: List[Tuple[int, int]],
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
        ppi: float = 96.0,
        default_height_mm: float = 0.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        h, w = frame_pattern.shape[:2]

        # 1. Difference and Threshold
        gray = cv2.cvtColor(frame_pattern, cv2.COLOR_BGR2GRAY)

        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(gray, (mx, my), (mx + mw, my + mh), 0, -1)

        # 2. Mask Out Areas Outside Projector FOV
        w_proj = map_system.width
        h_proj = map_system.height

        if projector_matrix is not None:
            mask = self._get_fov_mask(gray.shape, projector_matrix, (w_proj, h_proj))
            if mask is not None:
                gray = cv2.bitwise_and(gray, mask)

        # 3. Dynamic Thresholding
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)
        if max_val < self.SL_MIN_GRAY_VAL:
            thresh = np.zeros_like(gray)
        else:
            dynamic_thresh = max(
                self.SL_MIN_DYNAMIC_THRESH, max_val * self.SL_DYNAMIC_THRESH_FACTOR
            )
            _, thresh = cv2.threshold(gray, dynamic_thresh, 255, cv2.THRESH_BINARY)

        # 4. Extract Observed Centroids
        observed_points_cam = []
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] > 0 and cv2.contourArea(cnt) > self.SL_MIN_CONTOUR_AREA:
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                observed_points_cam.append((cx, cy))

        if not observed_points_cam:
            return []

        # 5. Project to Projector Space (with parallax correction)
        observed_points_proj = []
        ppi_mm = ppi / 25.4

        # We need a list for debug logging later that matches the old format (N, 1, 2)
        dst_pts_list = []

        for u, v in observed_points_cam:
            if self.camera_matrix is not None and self.R is not None:
                # Use 3D projection
                wx_mm, wy_mm = self._parallax_correction(u, v, default_height_mm)
                px = wx_mm * ppi_mm
                py = wy_mm * ppi_mm
            else:
                # Fallback to homography
                pt = np.array([u, v], dtype=np.float32).reshape(1, 1, 2)
                p_proj = cv2.perspectiveTransform(pt, projector_matrix)[0][0]
                px, py = p_proj[0], p_proj[1]

            if distortion_model:
                px, py = distortion_model.correct_theoretical_point(px, py)

            dst_pts_list.append([[px, py]])
            if 0 <= px <= w_proj and 0 <= py <= h_proj:
                observed_points_proj.append((px, py))

        dst_pts = np.array(dst_pts_list, dtype=np.float32)

        if self.debug_mode:
            self._log_sl_debug_data(
                frame_pattern,
                frame_dark,
                gray,
                thresh,
                max_val,
                dynamic_thresh,
                contours,
                observed_points_cam,
                dst_pts,
                w_proj,
                h_proj,
            )

        expected_arr = np.array(expected_points)
        if not observed_points_proj:
            return []

        # --- Global Drift Correction ---
        shifts = []
        for obs_p in observed_points_proj:
            dists = np.linalg.norm(expected_arr - np.array(obs_p), axis=1)
            idx = np.argmin(dists)
            nearest = expected_arr[idx]
            shifts.append(np.array(obs_p) - nearest)

        median_shift = np.median(np.array(shifts), axis=0)
        corrected_points = [
            tuple(np.array(p) - median_shift) for p in observed_points_proj
        ]

        detected_tokens_points = []
        for i, corr_p in enumerate(corrected_points):
            dists = np.linalg.norm(expected_arr - np.array(corr_p), axis=1)
            if np.min(dists) > self.SL_SHIFT_THRESHOLD_PX:
                detected_tokens_points.append(observed_points_proj[i])

        # --- Missing Dot Detection ---
        inv_proj_matrix = np.linalg.inv(projector_matrix)
        for exp_p in expected_points:
            pt = np.array([exp_p[0], exp_p[1]], dtype=np.float32).reshape(1, 1, 2)
            cam_p = cv2.perspectiveTransform(pt, inv_proj_matrix)[0][0]
            cx, cy = int(round(cam_p[0])), int(round(cam_p[1]))

            if 0 <= cx < w and 0 <= cy < h:
                if mask[cy, cx] == 255:
                    dists = np.linalg.norm(
                        np.array(corrected_points) - np.array(exp_p), axis=1
                    )
                    if np.min(dists) > self.SL_MISSING_THRESHOLD_PX:
                        detected_tokens_points.append(tuple(exp_p))

        # 5. Result Generation (Grid-based or Clustering)
        tokens = []
        if detected_tokens_points:
            if grid_spacing_svg > 0:
                # Phase 1: Convert all points to world coordinates
                world_points = []
                for p in detected_tokens_points:
                    wx, wy = map_system.screen_to_world(p[0], p[1])
                    world_points.append((wx, wy))

                # Phase 2: Cover areas with grid-sized continuous rectangles
                placed_rects = []
                remaining_pts = list(world_points)

                while len(remaining_pts) >= 2:
                    best_rect_center = None
                    best_count = 0
                    best_covered = []

                    # Find the dense center that covers the most points
                    for p in remaining_pts:
                        cx, cy = p
                        # Mean-shift to settle on the local centroid
                        for _ in range(5):
                            covered = []
                            for i, pt in enumerate(remaining_pts):
                                if (
                                    abs(pt[0] - cx) <= grid_spacing_svg / 2
                                    and abs(pt[1] - cy) <= grid_spacing_svg / 2
                                ):
                                    covered.append(i)

                            if not covered:
                                break

                            new_cx = sum(remaining_pts[i][0] for i in covered) / len(
                                covered
                            )
                            new_cy = sum(remaining_pts[i][1] for i in covered) / len(
                                covered
                            )

                            if abs(new_cx - cx) < 1.0 and abs(new_cy - cy) < 1.0:
                                cx, cy = new_cx, new_cy
                                break
                            cx, cy = new_cx, new_cy

                        if len(covered) > best_count:
                            best_count = len(covered)
                            best_rect_center = (cx, cy)
                            best_covered = covered

                    if best_count < 2:
                        break

                    placed_rects.append(
                        (best_rect_center[0], best_rect_center[1], best_count)
                    )

                    # Remove the covered points
                    for i in sorted(best_covered, reverse=True):
                        remaining_pts.pop(i)

                # Phase 3: Snap continuous rectangles to the grid
                occupied_cells = set()
                token_id = 1

                for cx, cy, count in placed_rects:
                    gx = int(math.floor((cx - grid_origin_x) / grid_spacing_svg))
                    gy = int(math.floor((cy - grid_origin_y) / grid_spacing_svg))

                    # Ensure no two tokens snap to the exact same cell
                    if (gx, gy) not in occupied_cells:
                        occupied_cells.add((gx, gy))
                        wx = grid_origin_x + (gx + 0.5) * grid_spacing_svg
                        wy = grid_origin_y + (gy + 0.5) * grid_spacing_svg
                        tokens.append(
                            Token(
                                id=token_id,
                                world_x=wx,
                                world_y=wy,
                                world_z=0.0,
                                marker_x=wx,
                                marker_y=wy,
                                marker_z=default_height_mm,
                                grid_x=gx,
                                grid_y=gy,
                                confidence=min(1.0, count / self.CONFIDENCE_SCALING),
                            )
                        )
                        token_id += 1
            else:
                clusters = []
                for p in detected_tokens_points:
                    added = False
                    for cluster in clusters:
                        centroid = np.mean(cluster, axis=0)
                        if (
                            np.linalg.norm(centroid - np.array(p))
                            < self.CLUSTER_DIST_PX
                        ):
                            cluster.append(p)
                            added = True
                            break
                    if not added:
                        clusters.append([p])

                token_id = 1
                for cluster in clusters:
                    centroid = np.mean(cluster, axis=0)
                    wx, wy = map_system.screen_to_world(centroid[0], centroid[1])
                    tokens.append(
                        Token(
                            id=token_id,
                            world_x=wx,
                            world_y=wy,
                            world_z=0.0,
                            marker_x=wx,
                            marker_y=wy,
                            marker_z=default_height_mm,
                            confidence=min(1.0, len(cluster) / self.CONFIDENCE_SCALING),
                        )
                    )
                    token_id += 1

        if self.debug_mode:
            self._handle_structured_light_debug(
                frame_pattern,
                projector_matrix,
                dst_pts,
                expected_arr,
                expected_points,
                tokens,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                gray,
            )

        return tokens

    def _handle_structured_light_debug(
        self,
        frame_pattern,
        projector_matrix,
        dst_pts,
        expected_arr,
        expected_points,
        tokens,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        gray,
    ):
        # Implementation adapted from TokenTracker
        debug_img = cv2.warpPerspective(
            frame_pattern, projector_matrix, (map_system.width, map_system.height)
        )
        debug_vectors = []
        for raw_p in dst_pts:
            p = tuple(raw_p[0])
            dists = np.linalg.norm(expected_arr - np.array(p), axis=1)
            idx = np.argmin(dists)
            nearest = tuple(expected_arr[idx])
            debug_vectors.append((p, nearest))

        self._save_sl_debug_image(
            debug_img,
            tokens,
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
            debug_vectors=debug_vectors,
            expected_points=expected_points,
        )

    def _log_sl_debug_data(
        self,
        frame_pattern,
        frame_dark,
        gray,
        thresh,
        max_val,
        dynamic_thresh,
        contours,
        observed_points_cam,
        dst_pts,
        w_proj,
        h_proj,
    ):
        h, w = frame_pattern.shape[:2]
        logging.debug("SL Debug: Camera Frame Res: %dx%d", w, h)
        logging.debug("SL Debug: Projector/Map Res: %dx%d", w_proj, h_proj)
        logging.debug(
            "SL Debug: Max Val: %d, Dynamic Thresh: %d", max_val, dynamic_thresh
        )
        logging.debug("SL Debug: Found %d raw contours.", len(contours))
        logging.debug(
            "SL Debug: Extracted %d observed centroids from %d contours.",
            len(observed_points_cam),
            len(contours),
        )
        if len(observed_points_cam) > 0:
            logging.debug("SL Debug: Sample Camera Coords: %s", observed_points_cam[:5])
        if len(dst_pts) > 0:
            logging.debug(
                "SL Debug: Sample Projector Coords: %s",
                [tuple(p[0]) for p in dst_pts[:5]],
            )

        # Save debug images
        timestamp = datetime.now().strftime("%H%M%S")
        cv2.imwrite(f"debug_sl_frame_pattern_{timestamp}.png", frame_pattern)
        cv2.imwrite(f"debug_sl_frame_dark_{timestamp}.png", frame_dark)

        diff = cv2.subtract(frame_pattern, frame_dark)
        cv2.imwrite(f"debug_sl_diff_{timestamp}.png", diff)

        cv2.imwrite(f"debug_sl_gray_{timestamp}.png", gray)
        cv2.imwrite(f"debug_sl_thresh_{timestamp}.png", thresh)
        logging.debug(
            "SL Debug: Saved debug images (frames, diff, gray, thresh) with timestamp %s",
            timestamp,
        )

    def _save_sl_debug_image(
        self,
        debug_img,
        tokens,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        debug_vectors=None,
        expected_points=None,
    ):
        h, w = debug_img.shape[:2]

        if debug_vectors:
            displacements = []
            radial_dists = []
            cx, cy = w / 2, h / 2
            for obs, exp in debug_vectors:
                dist = np.linalg.norm(np.array(obs) - np.array(exp))
                displacements.append(dist)
                radial_dists.append(np.linalg.norm(np.array(obs) - np.array([cx, cy])))
                color = (255, 0, 0) if dist <= 5.0 else (0, 0, 255)
                cv2.line(
                    debug_img,
                    (int(obs[0]), int(obs[1])),
                    (int(exp[0]), int(exp[1])),
                    color,
                    2,
                )

            if displacements:
                d_arr = np.array(displacements)
                r_arr = np.array(radial_dists)
                max_r = r_arr.max() if r_arr.size > 0 else 1.0
                logging.debug(
                    "\n--- Diagnostic Statistics ---\nTotal Points: %d\nDisplacement: Mean=%.2f, Median=%.2f\nZone 3 (Edge): %.2fpx",
                    len(d_arr),
                    d_arr.mean(),
                    np.median(d_arr),
                    d_arr[r_arr >= max_r * 0.66].mean(),
                )

        if expected_points:
            for ep in expected_points:
                cv2.circle(debug_img, (int(ep[0]), int(ep[1])), 3, (255, 255, 0), -1)

        if grid_spacing_svg > 0:
            DebugVisualizer.draw_grid(
                debug_img, map_system, grid_spacing_svg, grid_origin_x, grid_origin_y
            )

        DebugVisualizer.draw_tokens(debug_img, tokens, map_system)
        DebugVisualizer.save_debug_image("debug_token_detection_sl", debug_img)

    def _parallax_correction(self, u: float, v: float, h: float) -> Tuple[float, float]:
        """
        Intersects the ray from camera through (u, v) with the plane z = h.
        Returns (X, Y) in world space.
        """
        if self.camera_matrix is None or self.R is None:
            # Fallback if no 3D pose is available
            return 0.0, 0.0

        # 1. Back-project to ray in camera space
        p_pixel = np.array([u, v, 1.0]).reshape(3, 1)
        ray_cam = np.linalg.inv(self.camera_matrix) @ p_pixel

        # 2. Transform ray to world space
        v_world = self.R.T @ ray_cam
        v_world = v_world.flatten()

        # 3. Intersect with plane z = h
        cz = self.camera_center_world[2]
        vz = v_world[2]

        if abs(vz) < 1e-6:
            return 0.0, 0.0

        s = (h - cz) / vz
        if s < 0:
            return 0.0, 0.0

        p_world = self.camera_center_world + s * v_world
        return p_world[0], p_world[1]

    def _get_fov_mask(
        self,
        gray_shape: Tuple[int, int],
        projector_matrix: np.ndarray,
        map_dims: Tuple[int, int],
    ) -> Optional[np.ndarray]:
        """Caches and returns the projector FOV mask."""
        h, w = gray_shape
        params = (h, w, hash(projector_matrix.tobytes()), map_dims)

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
            cam_corners = cam_corners.astype(np.int32)

            mask = np.zeros(gray_shape, dtype=np.uint8)
            cv2.fillConvexPoly(mask, cam_corners, 255)
            self._fov_mask = mask
            self._fov_mask_params = params
            return mask
        except Exception:
            return None
