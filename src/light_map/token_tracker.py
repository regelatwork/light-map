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
    def __init__(self):
        self.debug_mode = False

    def get_scan_pattern(
        self, width: int, height: int, ppi: float
    ) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
        """
        Generates a jittered dot grid pattern for structured light detection.
        Returns: (pattern_image, list_of_expected_points_projector_space)
        """
        img = np.zeros((height, width, 3), dtype=np.uint8)
        expected_points = []

        # Increased spacing to account for low effective resolution (camera seeing small map)
        spacing = max(30, int(ppi * 0.8))

        # Constrain jitter to quarter-spacing to guarantee separation
        max_jitter = max(1, spacing // 4)

        for y in range(spacing // 2, height, spacing):
            for x in range(spacing // 2, width, spacing):
                jx = x + random.randint(-max_jitter, max_jitter)
                jy = y + random.randint(-max_jitter, max_jitter)

                # Ensure within bounds
                jx = max(0, min(width - 1, jx))
                jy = max(0, min(height - 1, jy))

                cv2.circle(img, (jx, jy), 4, (255, 255, 255), -1)
                expected_points.append((jx, jy))

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
            random.seed(42)
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
        if max_val < 30:
            thresh = np.zeros_like(gray)
        else:
            dynamic_thresh = max(40, max_val * 0.75)
            _, thresh = cv2.threshold(gray, dynamic_thresh, 255, cv2.THRESH_BINARY)

        # 4. Extract Observed Centroids
        observed_points_cam = []
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] > 0 and cv2.contourArea(cnt) > 2:
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

        SHIFT_THRESHOLD = 15.0
        detected_tokens_points = []
        for i, corr_p in enumerate(corrected_points):
            dists = np.linalg.norm(expected_arr - np.array(corr_p), axis=1)
            if np.min(dists) > SHIFT_THRESHOLD:
                detected_tokens_points.append(observed_points_proj[i])

        # 5. Clustering
        tokens = []
        if detected_tokens_points:
            CLUSTER_DIST = 80.0
            clusters = []
            for p in detected_tokens_points:
                added = False
                for cluster in clusters:
                    centroid = np.mean(cluster, axis=0)
                    if np.linalg.norm(centroid - np.array(p)) < CLUSTER_DIST:
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
                        confidence=min(1.0, len(cluster) / 3.0),
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
        h, w = frame_pattern.shape[:2]
        debug_img = cv2.warpPerspective(frame_pattern, projector_matrix, (w, h))
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
            frame_white, projector_matrix, mask_rois
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

    def _preprocess_and_find_markers(self, frame_white, projector_matrix, mask_rois):
        h, w = frame_white.shape[:2]
        warped = cv2.warpPerspective(frame_white, projector_matrix, (w, h))
        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(warped, (mx, my), (mx + mw, my + mh), (0, 0, 0), -1)
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 2)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 101, 10
        )
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
        closing = cv2.morphologyEx(
            opening, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=3
        )
        dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, 10.0, 255, 0)
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
            if cv2.countNonZero(blob_mask) < 300:
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
                    > 0.4
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
