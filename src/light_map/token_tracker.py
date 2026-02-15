import cv2
import numpy as np
from typing import List, Optional, Tuple
import math
from light_map.common_types import Token
from light_map.map_system import MapSystem


class TokenTracker:
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode

    def detect_tokens(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        frame_dark: Optional[np.ndarray] = None,
        grid_spacing_svg: float = 0.0,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        mask_rois: Optional[List[Tuple[int, int, int, int]]] = None,
        ppi: float = 0.0,
    ) -> List[Token]:
        if frame_white is None:
            return []

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

        return tokens

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
        cv2.rectangle(
            blob_bbox_mask, (x, y), (x + w_rect, y + h_rect), 255, -1
        )

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
