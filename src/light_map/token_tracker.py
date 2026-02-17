import cv2
import numpy as np
from typing import List, Optional, Tuple
import math
import random
from datetime import datetime
from light_map.common_types import Token, TokenDetectionAlgorithm
from light_map.map_system import MapSystem


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
        # Was 0.4, increasing to 0.8 (~1 inch spacing at 96 PPI)
        spacing = max(30, int(ppi * 0.8))

        # Constrain jitter to quarter-spacing to guarantee separation
        # max separation reduction = jitter_A + jitter_B = 2 * (S/4) = S/2
        # Min distance remaining = S - S/2 = S/2.
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
            # Generate expected points to pass to the detector
            # NOTE: We need to regenerate the exact same pattern that was projected.
            # This implies get_scan_pattern must be deterministic or we must pass the points in.
            # Ideally, the ScanningScene should pass the expected points.
            # For now, let's assume valid design requires deterministic generation or state passing.
            # Since we don't have state passing in existing signature, we might need to rely on seeded random
            # or simply changing the signature to accept expected_points.
            # BUT, for this task, let's re-generate.
            # CRITICAL: random.seed() must be consistent.
            # Alternatively, detect_tokens inputs should include expected_points.
            # As a quick fix, let's use a fixed seed based on time or just fixed seed 42 for now in get_scan_pattern if needed.
            # Actually, simpler: The pattern is static or generated deterministically.
            # Let's assume for now we call get_scan_pattern with a fixed seed inside the method or pass it.
            # To solve this robustly: ScanningScene should generate the pattern AND the points, then pass points to detect_tokens.
            # However, changing the signature too much might break things.
            # Let's seed with 42 before generation to be safe.

            random.seed(42)
            # CRITICAL FIX: Use Projector Resolution (from map_system) for expected points,
            # NOT Camera Resolution (frame_pattern.shape).
            # The projector_matrix transforms observed points to Projector Space (Screen Space).
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
            )
        else:
            return self._detect_flash(
                frame_pattern,
                projector_matrix,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                mask_rois,
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
    ) -> List[Token]:
        h, w = frame_pattern.shape[:2]

        # Debug: Print Frame Shape and Matrix
        if self.debug_mode:
            print(f"Debug: Input Frame Shape: {w}x{h}")
            m_flat = projector_matrix.flatten()
            print(
                f"Debug: Projector Matrix: [{m_flat[0]:.2f}, {m_flat[1]:.2f}, {m_flat[2]:.2f}]"
            )
            print(
                f"                        [{m_flat[3]:.2f}, {m_flat[4]:.2f}, {m_flat[5]:.2f}]"
            )
            print(
                f"                        [{m_flat[6]:.2f}, {m_flat[7]:.2f}, {m_flat[8]:.2f}]"
            )

        # 1. Difference and Threshold
        diff = cv2.subtract(frame_pattern, frame_dark)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(gray, (mx, my), (mx + mw, my + mh), 0, -1)

        # 2. Mask Out Areas Outside Projector FOV (Validity Mask)
        # This prevents bright reflections on the floor from skewing the threshold.
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
            # Apply mask to gray image (everything OUTSIDE becomes 0)
            gray = cv2.bitwise_and(gray, mask)

        except np.linalg.LinAlgError:
            print("Warning: Projector Matrix singular, cannot compute valid ROI mask.")

        # 3. Dynamic Thresholding
        # Fixed threshold (40) fails if the projector black level or ambient light difference is high.
        # We find the brightest pixel INSIDE THE VALID ROI and threshold relative to it.
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)

        # If signal is too weak (dots barely visible), fallback or fail
        if max_val < 30:
            thresh = np.zeros_like(gray)
        else:
            # Use 75% of peak brightness to prioritize the dot over the surface glow
            dynamic_thresh = max(40, max_val * 0.75)
            _, thresh = cv2.threshold(gray, dynamic_thresh, 255, cv2.THRESH_BINARY)

        if self.debug_mode:
            print(
                f"Debug: Max Diff Brightness (ROI): {max_val}. Threshold used: {dynamic_thresh if max_val >= 30 else '0'}"
            )

        # 4. Extract Observed Centroids (Camera Space)
        observed_points_cam = []
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            M = cv2.moments(cnt)
            if M["m00"] > 0 and cv2.contourArea(cnt) > 2:  # Filter noise
                cx = M["m10"] / M["m00"]
                cy = M["m01"] / M["m00"]
                observed_points_cam.append((cx, cy))

        # 3. Transform to Projector Space
        if not observed_points_cam:
            return []

        src_pts = np.array(observed_points_cam, dtype=np.float32).reshape(-1, 1, 2)
        dst_pts = cv2.perspectiveTransform(src_pts, projector_matrix)

        # Filter points that are outside the projector screen bounds
        # (This prevents background clutter from matching with the grid)
        w_proj = map_system.width
        h_proj = map_system.height

        # Debug: Print stats about observed points
        if len(dst_pts) > 0:
            xs = [p[0][0] for p in dst_pts]
            ys = [p[0][1] for p in dst_pts]
            if self.debug_mode:
                print(
                    f"Debug: Observed Points Range X:[{min(xs):.1f}, {max(xs):.1f}] Y:[{min(ys):.1f}, {max(ys):.1f}]"
                )
                print(f"Debug: Screen Bounds W:{w_proj} H:{h_proj}")

        observed_points_proj = []
        for p in dst_pts:
            px, py = p[0]
            if 0 <= px <= w_proj and 0 <= py <= h_proj:
                observed_points_proj.append((px, py))

        # 4. Identification (Disparity + Occlusion)
        expected_arr = np.array(expected_points)
        detected_tokens_points = []

        if not observed_points_proj:
            return []

        # --- Global Drift Correction ---
        shifts = []
        for obs_p in observed_points_proj:
            dists = np.linalg.norm(expected_arr - np.array(obs_p), axis=1)
            idx = np.argmin(dists)
            nearest = expected_arr[idx]
            shifts.append(np.array(obs_p) - nearest)

        shifts_arr = np.array(shifts)
        median_shift = np.median(shifts_arr, axis=0)  # (dx, dy)

        # Apply correction to bring potentially drifted points back to alignment
        corrected_points = [
            tuple(np.array(p) - median_shift) for p in observed_points_proj
        ]

        # Lowering to 15.0 to detect tokens (observed shift ~19px) despite floor noise (~16px)
        SHIFT_THRESHOLD = 15.0

        # Log max shift to help tune threshold
        all_shift_magnitudes = []
        for i, corr_p in enumerate(corrected_points):
            dists = np.linalg.norm(expected_arr - np.array(corr_p), axis=1)
            min_dist = np.min(dists)
            all_shift_magnitudes.append(min_dist)

        max_shift_observed = (
            np.max(all_shift_magnitudes) if all_shift_magnitudes else 0.0
        )
        print(
            f"Debug: Max Shift Candidate: {max_shift_observed:.2f}px. (Threshold: {SHIFT_THRESHOLD}px)"
        )

        for i, corr_p in enumerate(corrected_points):
            # Check distance to ALL expected points (using corrected position)
            dists = np.linalg.norm(expected_arr - np.array(corr_p), axis=1)
            min_dist = np.min(dists)

            if min_dist > SHIFT_THRESHOLD:
                # Use the ORIGINAL observed point for the token position
                detected_tokens_points.append(observed_points_proj[i])

        # 5. Clustering
        tokens = []
        if detected_tokens_points:
            # Basic clustering: grouping points that are close to each other
            # We use a distance threshold slightly larger than grid spacing
            # However, we don't know grid spacing perfectly here without recalculating from PPI.
            # Let's estimate spacing from expected_points or pass it.
            # For simplicity, let's use a fixed pixel distance for clustering, e.g. 30px
            CLUSTER_DIST = 80.0

            clusters = []
            for p in detected_tokens_points:
                added = False
                for cluster in clusters:
                    # Check distance to cluster center or any point
                    # Simple logic: dist to centroid
                    centroid = np.mean(cluster, axis=0)
                    if np.linalg.norm(centroid - np.array(p)) < CLUSTER_DIST:
                        cluster.append(p)
                        added = True
                        break
                if not added:
                    clusters.append([p])

            # Convert clusters to Tokens
            token_id = 1
            for cluster in clusters:
                if len(cluster) < 1:
                    continue

                centroid = np.mean(cluster, axis=0)
                # Transform Projector(screen) -> World
                # Wait, projector_matrix is Cam -> Proj.
                # Projector coordinates usually map 1:1 to Screen coordinates if calibrated well.
                # Assuming projector_matrix takes us to Screen Pixel Coordinates.
                wx, wy = map_system.screen_to_world(centroid[0], centroid[1])

                tokens.append(
                    Token(
                        id=token_id,
                        world_x=wx,
                        world_y=wy,
                        confidence=min(
                            1.0, len(cluster) / 3.0
                        ),  # Confidence increases with points
                    )
                )
                token_id += 1

        if self.debug_mode:
            # Warp the camera frame to projector space for alignment with overlays
            h, w = frame_pattern.shape[:2]
            debug_img = cv2.warpPerspective(frame_pattern, projector_matrix, (w, h))

            # Prepare debug vectors: Observed -> Nearest Expected
            # We want to see the RAW displacement (before drift correction) to diagnose the issue.
            # And maybe the corrected ones too?
            # Let's show:
            # - Green Line: Observed -> Nearest Expected (Raw Displacement)
            # - Yellow Circle: Expected Grid Point
            # - Red Cross: Observed Point

            # Re-find nearest for ALL points (unfiltered dst_pts) to see EVERYTHING
            debug_vectors = []
            for raw_p in dst_pts:
                p = tuple(raw_p[0])
                dists = np.linalg.norm(expected_arr - np.array(p), axis=1)
                idx = np.argmin(dists)
                nearest = tuple(expected_arr[idx])
                debug_vectors.append((p, nearest))

            self._save_debug_image(
                debug_img,
                np.zeros_like(gray),  # Markers not used here, pass empty
                tokens,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                debug_vectors=debug_vectors,
                expected_points=expected_points,  # Pass expected points
            )

        return tokens

    def _detect_flash(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
    ) -> List[Token]:
        # 1. Preprocess the image to find distinct regions (markers)
        warped_image, markers = self._preprocess_and_find_markers(
            frame_white, projector_matrix, mask_rois
        )

        # 2. Extract tokens from these regions
        tokens = self._extract_tokens_from_markers(
            warped_image,
            markers,
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
        )

        # 3. Save debug image if enabled
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
        base_image: np.ndarray,
        markers: np.ndarray,
        tokens: List[Token],
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        debug_vectors: Optional[
            List[Tuple[Tuple[float, float], Tuple[float, float]]]
        ] = None,
        expected_points: Optional[List[Tuple[int, int]]] = None,
    ):
        """Creates and saves an annotated image for debugging token detection."""
        debug_img = base_image.copy()
        h, w = debug_img.shape[:2]

        # 0. Draw Debug Vectors (Displacement Field)
        if debug_vectors:
            displacements = []
            radial_dists = []
            cx, cy = w / 2, h / 2

            for obs, exp in debug_vectors:
                # Color based on magnitude
                obs_arr = np.array(obs)
                exp_arr = np.array(exp)
                dist = np.linalg.norm(obs_arr - exp_arr)

                displacements.append(dist)
                radial_dists.append(np.linalg.norm(obs_arr - np.array([cx, cy])))

                color = (255, 0, 0)  # Blue (for small/good)
                if dist > 5.0:
                    color = (0, 0, 255)  # Red (for large/bad)

                p1 = (int(obs[0]), int(obs[1]))
                p2 = (int(exp[0]), int(exp[1]))

                # Thicker lines (2px)
                cv2.line(debug_img, p1, p2, color, 2)
                # cv2.circle(debug_img, p2, 2, (0, 255, 255), -1) # Yellow dot at Expected

            # --- Print Statistics ---
            if displacements:
                d_arr = np.array(displacements)
                r_arr = np.array(radial_dists)

                print("\n--- Diagnostic Statistics ---")
                print(f"Total Points: {len(d_arr)}")
                print(
                    f"Displacement: Min={d_arr.min():.2f}, Max={d_arr.max():.2f}, Mean={d_arr.mean():.2f}, Median={np.median(d_arr):.2f}"
                )

                # Frequency Histogram
                hist, bins = np.histogram(d_arr, bins=[0, 2, 5, 10, 20, 50, 100, 1000])
                print("Displacement Histogram:")
                for i in range(len(hist)):
                    print(f"  {bins[i]:.0f}-{bins[i + 1]:.0f}px: {hist[i]}")

                # Radial Correlation (Granular check for Barrel Distortion)
                # Split into 3 zones: Center (0-33%), Mid (33-66%), Edge (66-100%)
                max_r = np.max(r_arr) if len(r_arr) > 0 else 1.0

                mask_center = r_arr < (max_r * 0.33)
                mask_mid = (r_arr >= (max_r * 0.33)) & (r_arr < (max_r * 0.66))
                mask_edge = r_arr >= (max_r * 0.66)

                d_center = d_arr[mask_center]
                d_mid = d_arr[mask_mid]
                d_edge = d_arr[mask_edge]

                mean_center = d_center.mean() if len(d_center) > 0 else 0.0
                mean_mid = d_mid.mean() if len(d_mid) > 0 else 0.0
                mean_edge = d_edge.mean() if len(d_edge) > 0 else 0.0

                print("Radial Analysis (Barrel Distortion Check):")
                print(f"  Max Radius: {max_r:.1f}px")
                print(f"  Zone 1 (0-33%):  {mean_center:.2f}px (N={len(d_center)})")
                print(f"  Zone 2 (33-66%): {mean_mid:.2f}px (N={len(d_mid)})")
                print(f"  Zone 3 (66-100%):{mean_edge:.2f}px (N={len(d_edge)})")

                # Identify Max Displacement Location
                max_idx = np.argmax(d_arr)
                max_pt = debug_vectors[max_idx][0]
                print(
                    f"  Max Error Location: ({max_pt[0]:.0f}, {max_pt[1]:.0f}) -> {d_arr[max_idx]:.2f}px"
                )

                if mean_edge > mean_center * 1.5:
                    print("  -> LIKELY BARREL/KEYSTONE DISTORTION DETECTED")

                print("-----------------------------\n")

        # 0.5 Draw ALL Expected Points (to see the grid alignment)
        if expected_points:
            for ep in expected_points:
                cv2.circle(
                    debug_img, (int(ep[0]), int(ep[1])), 3, (255, 255, 0), -1
                )  # Cyan/Yellow dots (thicker 3px)

        # 1. Draw Grid Lines
        if grid_spacing_svg > 0:
            # Find the min/max world coordinates visible on screen
            corners_world = [
                map_system.screen_to_world(0, 0),
                map_system.screen_to_world(w, 0),
                map_system.screen_to_world(w, h),
                map_system.screen_to_world(0, h),
            ]
            min_wx = min(p[0] for p in corners_world)
            max_wx = max(p[0] for p in corners_world)
            min_wy = min(p[1] for p in corners_world)
            max_wy = max(p[1] for p in corners_world)

            min_gx = math.floor((min_wx - grid_origin_x) / grid_spacing_svg)
            max_gx = math.ceil((max_wx - grid_origin_x) / grid_spacing_svg)
            min_gy = math.floor((min_wy - grid_origin_y) / grid_spacing_svg)
            max_gy = math.ceil((max_wy - grid_origin_y) / grid_spacing_svg)

            for i in range(min_gx, max_gx + 1):
                wx = grid_origin_x + i * grid_spacing_svg
                p1_world = (wx, min_wy)
                p2_world = (wx, max_wy)
                p1_screen = map_system.world_to_screen(*p1_world)
                p2_screen = map_system.world_to_screen(*p2_world)
                cv2.line(
                    debug_img,
                    (int(p1_screen[0]), int(p1_screen[1])),
                    (int(p2_screen[0]), int(p2_screen[1])),
                    (100, 100, 100),
                    1,
                )
            for i in range(min_gy, max_gy + 1):
                wy = grid_origin_y + i * grid_spacing_svg
                p1_world = (min_wx, wy)
                p2_world = (max_wx, wy)
                p1_screen = map_system.world_to_screen(*p1_world)
                p2_screen = map_system.world_to_screen(*p2_world)
                cv2.line(
                    debug_img,
                    (int(p1_screen[0]), int(p1_screen[1])),
                    (int(p2_screen[0]), int(p2_screen[1])),
                    (100, 100, 100),
                    1,
                )

        # 2. Draw Blobs, BBoxes, and Numbers
        unique_markers = np.unique(markers)
        for marker_id in unique_markers:
            if marker_id <= 1:
                continue
            blob_mask = np.zeros(markers.shape, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            contours, _ = cv2.findContours(
                blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if not contours:
                continue

            # Draw contour
            cv2.drawContours(debug_img, contours, -1, (0, 255, 0), 1)

            # Draw bounding box and number
            x, y, w_rect, h_rect = cv2.boundingRect(contours[0])
            cv2.rectangle(debug_img, (x, y), (x + w_rect, y + h_rect), (255, 0, 0), 1)
            cv2.putText(
                debug_img,
                str(marker_id),
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2,
            )

        # 3. Draw Detected Token Circles
        for token in tokens:
            sx, sy = map_system.world_to_screen(token.world_x, token.world_y)
            cv2.circle(debug_img, (int(sx), int(sy)), 20, (0, 255, 255), 2)

        # 4. Save the image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"debug_token_detection_{timestamp}.png"
        cv2.imwrite(filename, debug_img)
        print(f"Saved debug image to {filename}")

    def _preprocess_and_find_markers(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Handles warping, masking, thresholding, and watershed marker generation."""
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

        kernel_open = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open, iterations=2)

        kernel_close = np.ones((7, 7), np.uint8)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel_close, iterations=3)

        dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, 10.0, 255, 0)
        sure_fg = np.uint8(sure_fg)

        sure_bg = cv2.dilate(closing, kernel_open, iterations=3)
        unknown = cv2.subtract(sure_bg, sure_fg)

        _, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0
        markers = cv2.watershed(warped, markers)

        return warped, markers

    def _extract_tokens_from_markers(
        self,
        warped_image: np.ndarray,
        markers: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
    ) -> List[Token]:
        """Iterates through markers to find blobs and convert them to Tokens."""
        tokens = []
        token_id_counter = 1
        found_grid_cells = set()
        gray = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY)

        unique_markers = np.unique(markers)
        for marker_id in unique_markers:
            if marker_id <= 1:  # Skip background and unknown regions
                continue

            blob_mask = np.zeros_like(gray, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            if cv2.countNonZero(blob_mask) < 300:  # Area threshold
                continue

            if grid_spacing_svg > 0:
                # --- Grid Coverage Logic ---
                self._process_blob_with_grid(
                    blob_mask,
                    map_system,
                    grid_spacing_svg,
                    grid_origin_x,
                    grid_origin_y,
                    tokens,
                    found_grid_cells,
                    token_id_counter,
                )
                token_id_counter += len(tokens) - (token_id_counter - 1)
            else:
                # --- No-Grid Fallback: Use Centroid ---
                self._process_blob_with_centroid(
                    blob_mask, map_system, tokens, token_id_counter
                )
                token_id_counter += 1
        return tokens

    def _process_blob_with_grid(
        self,
        blob_mask: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        tokens: List[Token],
        found_grid_cells: set,
        token_id_counter: int,
    ):
        """Calculates token positions based on grid cell coverage."""
        x, y, w_rect, h_rect = cv2.boundingRect(blob_mask)
        screen_points = np.float32(
            [[x, y], [x + w_rect, y], [x, y + h_rect], [x + w_rect, y + h_rect]]
        ).reshape(-1, 1, 2)

        world_coords = [
            map_system.screen_to_world(p[0][0], p[0][1]) for p in screen_points
        ]
        world_x_coords = [p[0] for p in world_coords]
        world_y_coords = [p[1] for p in world_coords]

        min_gx = (
            math.floor((min(world_x_coords) - grid_origin_x) / grid_spacing_svg) - 1
        )
        max_gx = math.ceil((max(world_x_coords) - grid_origin_x) / grid_spacing_svg) + 1
        min_gy = (
            math.floor((min(world_y_coords) - grid_origin_y) / grid_spacing_svg) - 1
        )
        max_gy = math.ceil((max(world_y_coords) - grid_origin_y) / grid_spacing_svg) + 1

        # Create a filled mask from the blob's bounding box
        blob_bbox_mask = np.zeros_like(blob_mask)
        cv2.rectangle(blob_bbox_mask, (x, y), (x + w_rect, y + h_rect), 255, -1)

        for gx in range(min_gx, max_gx):
            for gy in range(min_gy, max_gy):
                if (gx, gy) in found_grid_cells:
                    continue

                cell_tl_wx = grid_origin_x + gx * grid_spacing_svg
                cell_tl_wy = grid_origin_y + gy * grid_spacing_svg
                cell_br_wx = cell_tl_wx + grid_spacing_svg
                cell_br_wy = cell_tl_wy + grid_spacing_svg

                cell_world_points = [
                    (cell_tl_wx, cell_tl_wy),
                    (cell_br_wx, cell_tl_wy),
                    (cell_br_wx, cell_br_wy),
                    (cell_tl_wx, cell_br_wy),
                ]
                cell_screen_points = np.array(
                    [map_system.world_to_screen(p[0], p[1]) for p in cell_world_points],
                    dtype=np.int32,
                )

                cell_mask = np.zeros_like(blob_mask)
                cv2.fillConvexPoly(cell_mask, cell_screen_points, 255)
                cell_area = cv2.countNonZero(cell_mask)

                if cell_area == 0:
                    continue

                # Intersect the BBOX mask with the cell mask
                intersection_area = cv2.countNonZero(
                    cv2.bitwise_and(blob_bbox_mask, cell_mask)
                )
                coverage = intersection_area / cell_area

                if coverage > 0.4:
                    token_wx = grid_origin_x + (gx + 0.5) * grid_spacing_svg
                    token_wy = grid_origin_y + (gy + 0.5) * grid_spacing_svg
                    tokens.append(
                        Token(
                            id=token_id_counter + len(tokens),
                            world_x=token_wx,
                            world_y=token_wy,
                            grid_x=gx,
                            grid_y=gy,
                            confidence=coverage,
                        )
                    )
                    found_grid_cells.add((gx, gy))

    def _process_blob_with_centroid(
        self,
        blob_mask: np.ndarray,
        map_system: MapSystem,
        tokens: List[Token],
        token_id_counter: int,
    ):
        """Calculates a single token position from the blob's centroid."""
        M = cv2.moments(blob_mask)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            wx, wy = map_system.screen_to_world(cx, cy)
            tokens.append(
                Token(
                    id=token_id_counter,
                    world_x=wx,
                    world_y=wy,
                    grid_x=None,
                    grid_y=None,
                    confidence=1.0,
                )
            )
