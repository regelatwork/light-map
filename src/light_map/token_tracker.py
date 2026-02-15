import cv2
import numpy as np
from typing import List, Optional, Tuple
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
        """
        Detects tokens in the given frame(s) and maps them to world coordinates.
        'mask_rois' is a list of (x, y, w, h) in projector space to mask out.
        'ppi' is used to estimate physical token size for splitting adjacent blobs.
        """
        if frame_white is None:
            return []

        # 1. Preprocessing & Warp
        h, w = frame_white.shape[:2]
        warped = cv2.warpPerspective(frame_white, projector_matrix, (w, h))

        # Apply Masks (Projector Space)
        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(warped, (mx, my), (mx + mw, my + mh), (255, 255, 255), -1)

        # Blur first to reduce noise and internal texture
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 2)

        # Threshold
        # Use Adaptive Thresholding to handle uneven lighting/shadows
        # block_size=101 (large enough to cover a token + margin), C=10
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 101, 10
        )

        # Morphological operations to remove noise
        # Open first to remove small noise
        kernel_open = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open, iterations=2)

        # Close aggressively to connect split parts (fix "donut" effect from glare)
        # Using larger kernel (7x7) to bridge gaps of ~15-20 pixels
        kernel_close = np.ones((7, 7), np.uint8)
        closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel_close, iterations=3)

        # Sure background area
        sure_bg = cv2.dilate(closing, kernel_open, iterations=3)

        # Finding sure foreground area (Distance Transform)
        dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)

        # Use fixed threshold for sure foreground instead of relative max
        # Assuming min token radius ~10px (at 54 PPI, this is ~0.4 inch diameter)
        # This ensures we catch small tokens even if a large blob exists
        _, sure_fg = cv2.threshold(dist_transform, 10.0, 255, 0)

        # Finding unknown region
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(sure_bg, sure_fg)

        # Marker labelling
        ret, markers = cv2.connectedComponents(sure_fg)
        # Add one to all labels so that sure background is not 0, but 1
        markers = markers + 1
        # Now, mark the region of unknown with zero
        markers[unknown == 255] = 0

        # Watershed
        markers = cv2.watershed(warped, markers)

        # Extract Tokens
        tokens = []
        unique_markers = np.unique(markers)

        token_id_counter = 1

        for marker_id in unique_markers:
            if marker_id <= 1:  # 0 is unknown, 1 is background. -1 is boundary.
                continue

            # Create a mask for this object
            mask = np.zeros_like(gray, dtype=np.uint8)
            mask[markers == marker_id] = 255

            # Filter by Area
            area = cv2.countNonZero(mask)
            if area < 300:  # Ignore noise < ~0.5 inch diameter
                continue

            # Bounding Rect
            x, y, w_rect, h_rect = cv2.boundingRect(mask)

            # Determine how many tokens are in this blob
            num_tokens_x = 1
            num_tokens_y = 1

            if ppi > 0:
                # Aspect Ratio Logic
                # Using 1.6 as threshold (significantly more than 1.0)
                if h_rect > 1.6 * w_rect:
                    num_tokens_y = 2
                elif w_rect > 1.6 * h_rect:
                    num_tokens_x = 2

            # Create tokens
            step_x = w_rect / num_tokens_x
            step_y = h_rect / num_tokens_y

            for i in range(num_tokens_x):
                for j in range(num_tokens_y):
                    # Local center in rect
                    sub_cx = x + (step_x * i) + (step_x / 2)
                    sub_cy = y + (step_y * j) + (step_y / 2)

                    wx, wy = map_system.screen_to_world(sub_cx, sub_cy)

                    # Grid Snapping
                    grid_x, grid_y = None, None
                    if grid_spacing_svg > 0:
                        gx = round((wx - grid_origin_x) / grid_spacing_svg)
                        gy = round((wy - grid_origin_y) / grid_spacing_svg)

                        snapped_wx = gx * grid_spacing_svg + grid_origin_x
                        snapped_wy = gy * grid_spacing_svg + grid_origin_y
                        dist = np.sqrt((wx - snapped_wx) ** 2 + (wy - snapped_wy) ** 2)

                        if dist < (0.4 * grid_spacing_svg):
                            grid_x = int(gx)
                            grid_y = int(gy)
                            # Enforce grid alignment
                            wx = snapped_wx
                            wy = snapped_wy

                    tokens.append(
                        Token(
                            id=token_id_counter,
                            world_x=wx,
                            world_y=wy,
                            grid_x=grid_x,
                            grid_y=grid_y,
                            confidence=1.0 / (num_tokens_x * num_tokens_y),
                        )
                    )
                    token_id_counter += 1

        # Deduplicate tokens that snapped to the same grid cell
        if grid_spacing_svg > 0:
            unique_tokens = {}
            for token in tokens:
                if token.grid_x is not None and token.grid_y is not None:
                    # Key by grid coordinate tuple
                    key = (token.grid_x, token.grid_y)
                    if key not in unique_tokens:
                        unique_tokens[key] = token
                else:
                    # For tokens not on the grid, use a placeholder key to keep them
                    unique_tokens[(token.id, -1)] = token
            return list(unique_tokens.values())

        return tokens
