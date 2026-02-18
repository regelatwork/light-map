import cv2
import numpy as np
from typing import List, Optional, Tuple, TYPE_CHECKING
import math
import random
from datetime import datetime
from light_map.common_types import Token, TokenDetectionAlgorithm
from light_map.map_system import MapSystem

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel


class TokenTracker:
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

    # --- Flash Detection Parameters ---
    FLASH_GAUSSIAN_BLUR = (9, 9)
    FLASH_ADAPTIVE_BLOCK_SIZE = 101
    FLASH_ADAPTIVE_C = 10
    FLASH_MORPH_OPEN_ITER = 2
    FLASH_MORPH_CLOSE_ITER = 3
    FLASH_DISTANCE_THRESH = 10.0
    FLASH_MIN_BLOB_AREA = 300

    # --- Clustering & Result Parameters ---
    CLUSTER_DIST_PX = 80.0
    CONFIDENCE_SCALING = 3.0
    GRID_OVERLAP_THRESHOLD = 0.4

    def __init__(self):
        self.debug_mode = False

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

        row_idx = 0
        for y in range(spacing // 2, height, row_spacing):
            # Stagger every other row
            x_offset = (spacing // 2) if (row_idx % 2 == 1) else 0

            for x in range(spacing // 2 + x_offset, width, spacing):
                jx = x + random.randint(-max_jitter, max_jitter)
                jy = y + random.randint(-max_jitter, max_jitter)

                # Ensure within bounds with margin to avoid straddling the border
                jx = max(self.SL_EDGE_MARGIN, min(width - 1 - self.SL_EDGE_MARGIN, jx))
                jy = max(self.SL_EDGE_MARGIN, min(height - 1 - self.SL_EDGE_MARGIN, jy))

                cv2.circle(img, (jx, jy), self.SL_DOT_RADIUS, (255, 255, 255), -1)
                expected_points.append((jx, jy))

            row_idx += 1

        return img, expected_points

    def detect_tokens(
        self,
        frame_white: Optional[np.ndarray] = None,
        frame_pattern: Optional[np.ndarray] = None,
        frame_dark: Optional[np.ndarray] = None,
        projector_matrix: Optional[np.ndarray] = None,
        map_system: Optional[MapSystem] = None,
        grid_spacing_svg: float = 0.0,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        mask_rois: Optional[List[Tuple[int, int, int, int]]] = None,
        ppi: float = 96.0,
        algorithm: TokenDetectionAlgorithm = TokenDetectionAlgorithm.FLASH,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        # Handle case where only one frame is passed (default to frame_pattern for SL or frame_white for Flash)
        if frame_pattern is None and frame_white is not None:
            frame_pattern = frame_white
        if frame_white is None and frame_pattern is not None:
            frame_white = frame_pattern

        if frame_white is None:
            return []

        if (
            algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT
            and frame_dark is not None
        ):
            random.seed(self.SL_SEED)
            w_proj = map_system.width
            h_proj = map_system.height
            _, expected_points = self.get_scan_pattern(w_proj, h_proj, ppi)

            return self._detect_structured_light(
                frame_pattern,
                frame_dark,
                expected_points,
                projector_matrix,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                mask_rois,
                distortion_model=distortion_model,
            )
        else:
            return self._detect_flash(
                frame_white,
                projector_matrix,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                mask_rois,
                distortion_model=distortion_model,
            )

    def _detect_structured_light(
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
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        h, w = frame_pattern.shape[:2]

        # 1. Difference and Threshold
        diff = cv2.subtract(frame_pattern, frame_dark)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(gray, (mx, my), (mx + mw, my + mh), 0, -1)

        # 2. Mask Out Areas Outside Projector FOV
        w_proj = map_system.width
        h_proj = map_system.height
        try:
            inv_proj_matrix = np.linalg.inv(projector_matrix)
            proj_corners = np.array(
                [[0, 0], [w_proj, 0], [w_proj, h_proj], [0, h_proj]], dtype=np.float32
            ).reshape(-1, 1, 2)
            cam_corners = cv2.perspectiveTransform(proj_corners, inv_proj_matrix)
            cam_corners = cam_corners.astype(np.int32)

            mask = np.zeros_like(gray)
            cv2.fillConvexPoly(mask, cam_corners, 255)
            gray = cv2.bitwise_and(gray, mask)
        except np.linalg.LinAlgError:
            pass

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

        src_pts = np.array(observed_points_cam, dtype=np.float32).reshape(-1, 1, 2)
        if distortion_model:
            dst_pts = distortion_model.apply_correction(src_pts)
        else:
            dst_pts = cv2.perspectiveTransform(src_pts, projector_matrix)

        observed_points_proj = []
        for p in dst_pts:
            px, py = p[0]
            if 0 <= px <= w_proj and 0 <= py <= h_proj:
                observed_points_proj.append((px, py))

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
        # Identify expected dots that SHOULD be visible but have no corresponding observed dot.
        # This handles shadows and absorbent materials (black tokens).
        inv_proj_matrix = np.linalg.inv(projector_matrix)
        for exp_p in expected_points:
            # Transform expected projector point to camera space to check visibility
            pt = np.array([exp_p[0], exp_p[1]], dtype=np.float32).reshape(1, 1, 2)
            cam_p = cv2.perspectiveTransform(pt, inv_proj_matrix)[0][0]
            cx, cy = int(round(cam_p[0])), int(round(cam_p[1]))

            # Check if in camera frame and within the projector FOV mask
            if 0 <= cx < w and 0 <= cy < h:
                if mask[cy, cx] == 255:
                    # Visible! Now check if any corrected observed point is near it.
                    dists = np.linalg.norm(
                        np.array(corrected_points) - np.array(exp_p), axis=1
                    )
                    if np.min(dists) > self.SL_MISSING_THRESHOLD_PX:
                        # This expected dot is missing -> likely a token shadow or black material.
                        detected_tokens_points.append(tuple(exp_p))

        # 5. Result Generation (Grid-based or Clustering)
        tokens = []
        if detected_tokens_points:
            if grid_spacing_svg > 0:
                # Group by grid cell for precise adjacent token detection
                cell_map = {}  # (gx, gy) -> list of points
                for p in detected_tokens_points:
                    wx, wy = map_system.screen_to_world(p[0], p[1])
                    gx = int(math.floor((wx - grid_origin_x) / grid_spacing_svg))
                    gy = int(math.floor((wy - grid_origin_y) / grid_spacing_svg))
                    if (gx, gy) not in cell_map:
                        cell_map[(gx, gy)] = []
                    cell_map[(gx, gy)].append(p)

                token_id = 1
                for (gx, gy), cluster in cell_map.items():
                    # Minimum evidence threshold (e.g. at least 2 points shifted/missing in this cell)
                    if len(cluster) >= 2:
                        # Centered in the cell
                        tokens.append(
                            Token(
                                id=token_id,
                                world_x=grid_origin_x + (gx + 0.5) * grid_spacing_svg,
                                world_y=grid_origin_y + (gy + 0.5) * grid_spacing_svg,
                                grid_x=gx,
                                grid_y=gy,
                                confidence=min(
                                    1.0, len(cluster) / self.CONFIDENCE_SCALING
                                ),
                            )
                        )
                        token_id += 1
            else:
                # Fallback to Euclidean clustering for off-grid detection
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

        self._save_debug_image(
            debug_img,
            np.zeros_like(gray),
            tokens,
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
            debug_vectors=debug_vectors,
            expected_points=expected_points,
        )

    def _detect_flash(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
        distortion_model: Optional["ProjectorDistortionModel"] = None,
    ) -> List[Token]:
        warped_image, markers = self._preprocess_and_find_markers(
            frame_white,
            projector_matrix,
            mask_rois,
            map_system.width,
            map_system.height,
        )
        tokens = self._extract_tokens_from_markers(
            warped_image,
            markers,
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
            distortion_model=distortion_model,
        )
        if self.debug_mode:
            self._save_debug_image(
                warped_image,
                markers,
                tokens,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
            )
        return tokens

    def _save_debug_image(
        self,
        base_image,
        markers,
        tokens,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        debug_vectors=None,
        expected_points=None,
    ):
        debug_img = base_image.copy()
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
                print(
                    f"\n--- Diagnostic Statistics ---\nTotal Points: {len(d_arr)}\nDisplacement: Mean={d_arr.mean():.2f}, Median={np.median(d_arr):.2f}\nZone 3 (Edge): {d_arr[r_arr >= max_r * 0.66].mean():.2f}px"
                )

        if expected_points:
            for ep in expected_points:
                cv2.circle(debug_img, (int(ep[0]), int(ep[1])), 3, (255, 255, 0), -1)

        # Draw Grid
        if grid_spacing_svg > 0:
            grid_color = (100, 100, 100)
            # Find world bounds to draw enough lines
            p_top_left = map_system.screen_to_world(0, 0)
            p_top_right = map_system.screen_to_world(w, 0)
            p_bot_left = map_system.screen_to_world(0, h)
            p_bot_right = map_system.screen_to_world(w, h)

            min_wx = min(p_top_left[0], p_top_right[0], p_bot_left[0], p_bot_right[0])
            max_wx = max(p_top_left[0], p_top_right[0], p_bot_left[0], p_bot_right[0])
            min_wy = min(p_top_left[1], p_top_right[1], p_bot_left[1], p_bot_right[1])
            max_wy = max(p_top_left[1], p_top_right[1], p_bot_left[1], p_bot_right[1])

            # Draw vertical lines
            start_gx = int(math.floor((min_wx - grid_origin_x) / grid_spacing_svg))
            end_gx = int(math.ceil((max_wx - grid_origin_x) / grid_spacing_svg))
            for gx in range(start_gx, end_gx + 1):
                wx = grid_origin_x + gx * grid_spacing_svg
                p1_s = map_system.world_to_screen(wx, min_wy)
                p2_s = map_system.world_to_screen(wx, max_wy)
                cv2.line(
                    debug_img,
                    (int(p1_s[0]), int(p1_s[1])),
                    (int(p2_s[0]), int(p2_s[1])),
                    grid_color,
                    1,
                )

            # Draw horizontal lines
            start_gy = int(math.floor((min_wy - grid_origin_y) / grid_spacing_svg))
            end_gy = int(math.ceil((max_wy - grid_origin_y) / grid_spacing_svg))
            for gy in range(start_gy, end_gy + 1):
                wy = grid_origin_y + gy * grid_spacing_svg
                p1_s = map_system.world_to_screen(min_wx, wy)
                p2_s = map_system.world_to_screen(max_wx, wy)
                cv2.line(
                    debug_img,
                    (int(p1_s[0]), int(p1_s[1])),
                    (int(p2_s[0]), int(p2_s[1])),
                    grid_color,
                    1,
                )

        # Draw Grid, Markers, Tokens
        unique_markers = np.unique(markers)
        for marker_id in unique_markers:
            if marker_id <= 1:
                continue
            blob_mask = np.zeros(markers.shape, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            contours, _ = cv2.findContours(
                blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                cv2.drawContours(debug_img, contours, -1, (0, 255, 0), 1)
                x, y, wr, hr = cv2.boundingRect(contours[0])
                cv2.rectangle(debug_img, (x, y), (x + wr, y + hr), (255, 0, 0), 1)

        for token in tokens:
            sx, sy = map_system.world_to_screen(token.world_x, token.world_y)
            cv2.circle(debug_img, (int(sx), int(sy)), 20, (0, 255, 255), 2)

        filename = (
            f"debug_token_detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        cv2.imwrite(filename, debug_img)

    def _preprocess_and_find_markers(
        self, frame_white, projector_matrix, mask_rois, target_w, target_h
    ):
        warped = cv2.warpPerspective(
            frame_white, projector_matrix, (target_w, target_h)
        )
        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(warped, (mx, my), (mx + mw, my + mh), (0, 0, 0), -1)
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.FLASH_GAUSSIAN_BLUR, 2)
        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            self.FLASH_ADAPTIVE_BLOCK_SIZE,
            self.FLASH_ADAPTIVE_C,
        )
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(
            thresh, cv2.MORPH_OPEN, kernel, iterations=self.FLASH_MORPH_OPEN_ITER
        )
        closing = cv2.morphologyEx(
            opening,
            cv2.MORPH_CLOSE,
            np.ones((7, 7), np.uint8),
            iterations=self.FLASH_MORPH_CLOSE_ITER,
        )
        dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, self.FLASH_DISTANCE_THRESH, 255, 0)
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(cv2.dilate(closing, kernel, iterations=3), sure_fg)
        _, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0
        return warped, cv2.watershed(warped, markers)

    def _extract_tokens_from_markers(
        self,
        warped_image,
        markers,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        distortion_model=None,
    ):
        tokens = []
        id_counter = 1
        found_cells = set()
        gray = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY)
        for marker_id in np.unique(markers):
            if marker_id <= 1:
                continue
            blob_mask = np.zeros_like(gray, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            if cv2.countNonZero(blob_mask) < self.FLASH_MIN_BLOB_AREA:
                continue
            if grid_spacing_svg > 0:
                self._process_blob_with_grid(
                    blob_mask,
                    map_system,
                    grid_spacing_svg,
                    grid_origin_x,
                    grid_origin_y,
                    tokens,
                    found_cells,
                    id_counter,
                    distortion_model,
                )
                id_counter = len(tokens) + 1
            else:
                self._process_blob_with_centroid(
                    blob_mask, map_system, tokens, id_counter, distortion_model
                )
                id_counter += 1
        return tokens

    def _process_blob_with_grid(
        self,
        blob_mask,
        map_system,
        spacing,
        ox,
        oy,
        tokens,
        found_cells,
        id_start,
        distortion_model=None,
    ):
        x, y, w, h = cv2.boundingRect(blob_mask)
        pts = np.float32([[x, y], [x + w, y], [x, y + h], [x + w, y + h]]).reshape(
            -1, 1, 2
        )
        world_pts = []
        for p in pts:
            sx, sy = p[0]
            if distortion_model:
                sx, sy = distortion_model.correct_theoretical_point(sx, sy)
            world_pts.append(map_system.screen_to_world(sx, sy))

        min_gx = math.floor((min(p[0] for p in world_pts) - ox) / spacing) - 1
        max_gx = math.ceil((max(p[0] for p in world_pts) - ox) / spacing) + 1
        min_gy = math.floor((min(p[1] for p in world_pts) - oy) / spacing) - 1
        max_gy = math.ceil((max(p[1] for p in world_pts) - oy) / spacing) + 1

        # TODO: A user mentioned that using a bounding box is actually more robust for
        # token detection than using the precise blob shape. Re-evaluate if we ever move
        # back to blob-based masking.
        bbox_mask = np.zeros_like(blob_mask)
        cv2.rectangle(bbox_mask, (x, y), (x + w, y + h), 255, -1)

        for gx in range(min_gx, max_gx):
            for gy in range(min_gy, max_gy):
                if (gx, gy) in found_cells:
                    continue
                cw_pts = [
                    (ox + gx * spacing, oy + gy * spacing),
                    (ox + (gx + 1) * spacing, oy + gy * spacing),
                    (ox + (gx + 1) * spacing, oy + (gy + 1) * spacing),
                    (ox + gx * spacing, oy + (gy + 1) * spacing),
                ]
                cs_pts = np.array(
                    [map_system.world_to_screen(p[0], p[1]) for p in cw_pts],
                    dtype=np.int32,
                )
                c_mask = np.zeros_like(blob_mask)
                cv2.fillConvexPoly(c_mask, cs_pts, 255)
                c_area = cv2.countNonZero(c_mask)
                if (
                    c_area > 0
                    and cv2.countNonZero(cv2.bitwise_and(bbox_mask, c_mask)) / c_area
                    > self.GRID_OVERLAP_THRESHOLD
                ):
                    tokens.append(
                        Token(
                            id=id_start + len(tokens),
                            world_x=ox + (gx + 0.5) * spacing,
                            world_y=oy + (gy + 0.5) * spacing,
                            grid_x=gx,
                            grid_y=gy,
                            confidence=1.0,
                        )
                    )
                    found_cells.add((gx, gy))

    def _process_blob_with_centroid(
        self, blob_mask, map_system, tokens, id_counter, distortion_model=None
    ):
        M = cv2.moments(blob_mask)
        if M["m00"] > 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            if distortion_model:
                cx, cy = distortion_model.correct_theoretical_point(cx, cy)
            wx, wy = map_system.screen_to_world(cx, cy)
            tokens.append(
                Token(
                    id=id_counter + len(tokens), world_x=wx, world_y=wy, confidence=1.0
                )
            )
