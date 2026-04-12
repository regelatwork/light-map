from __future__ import annotations
import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker

if TYPE_CHECKING:
    from light_map.core.common_types import Token
    from light_map.map.map_config import MapConfigManager


class VisibilityEngine:
    """
    Calculates visibility masks based on high-resolution blocker grids.
    Ensures watertight walls and supports corner peeking.
    """

    def __init__(
        self, grid_spacing_svg: float, grid_origin: Tuple[float, float] = (0.0, 0.0)
    ):
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin = grid_origin
        self.blockers: List[VisibilityBlocker] = []

        # Mask Cache: (token_id, grid_x, grid_y, size) -> np.ndarray
        self.mask_cache: Dict[Tuple[int, int, int, int], np.ndarray] = {}

        self.blocker_mask: Optional[np.ndarray] = None
        self.svg_to_mask_scale = 16.0 / grid_spacing_svg

    @property
    def width(self) -> int:
        """Returns the width of the visibility mask in pixels."""
        return self.blocker_mask.shape[1] if self.blocker_mask is not None else 0

    @property
    def height(self) -> int:
        """Returns the height of the visibility mask in pixels."""
        return self.blocker_mask.shape[0] if self.blocker_mask is not None else 0

    def calculate_mask_dimensions(self, svg_w: float, svg_h: float) -> Tuple[int, int]:
        """Calculates mask dimensions (1/16th inch per pixel) for a given SVG size."""
        return int(svg_w * self.svg_to_mask_scale), int(svg_h * self.svg_to_mask_scale)

    def update_blockers(
        self,
        blockers: List[VisibilityBlocker],
        mask_width: int = 0,
        mask_height: int = 0,
    ):
        """
        Renders a high-resolution blocker mask from SVG blockers.
        """
        self.blockers = blockers
        self.mask_cache = {}

        if mask_width > 0 and mask_height > 0:
            self.blocker_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)

        for blocker in blockers:
            # Convert flattened segments into pairs of points
            points = blocker.points
            if len(points) < 2:
                continue

            # Render blocker mask if dimensions provided
            if self.blocker_mask is not None:
                # Windows are transparent to vision
                if blocker.type != VisibilityType.WINDOW:
                    # Doors only block when NOT open
                    if blocker.type != VisibilityType.DOOR or not blocker.is_open:
                        mask_points = []
                        for px, py in points:
                            mx = int(px * self.svg_to_mask_scale)
                            my = int(py * self.svg_to_mask_scale)
                            mask_points.append((mx, my))

                        for i in range(len(mask_points) - 1):
                            p1 = mask_points[i]
                            p2 = mask_points[i + 1]
                            # 2px width + Round Caps
                            cv2.line(self.blocker_mask, p1, p2, 255, thickness=2)
                            cv2.circle(self.blocker_mask, p1, 1, 255, -1)
                            cv2.circle(self.blocker_mask, p2, 1, 255, -1)

    def _calculate_token_footprint(
        self, cx_mask: int, cy_mask: int, size: int
    ) -> np.ndarray:
        """
        Calculates the token's 'light source' footprint.
        Uses BFS to find pixels within (size/2 * 16 + 1) that are not blocked by walls.
        """
        if self.blocker_mask is None:
            # Fallback if no map loaded or blockers not updated
            return np.zeros((1, 1), dtype=np.uint8)

        h, w = self.blocker_mask.shape
        footprint = np.zeros((h, w), dtype=np.uint8)

        if not (0 <= cx_mask < w and 0 <= cy_mask < h):
            return footprint

        # Range limit: half-size in pixels + 1px overhang
        # size 1 -> 16px wide -> 8px radius + 1px = 9px
        range_limit = (size * 16 // 2) + 1

        queue = [(cy_mask, cx_mask)]
        footprint[cy_mask, cx_mask] = 255
        idx = 0

        while idx < len(queue):
            y, x = queue[idx]
            idx += 1

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx

                if 0 <= nx < w and 0 <= ny < h:
                    if footprint[ny, nx] == 0:
                        # Check distance constraint (Manhattan or Chebyshev is faster,
                        # but L-infinity/square is what we want for grid cells)
                        if (
                            abs(nx - cx_mask) <= range_limit
                            and abs(ny - cy_mask) <= range_limit
                        ):
                            # Check if not a wall
                            if self.blocker_mask[ny, nx] == 0:
                                footprint[ny, nx] = 255
                                queue.append((ny, nx))

        return footprint

    def _calculate_visibility_mask(
        self,
        source_points: List[Tuple[int, int]],
        vision_range_px: int,
        mask_w: int,
        mask_h: int,
    ) -> np.ndarray:
        """
        Calculates a unioned visibility mask from multiple source points.
        Uses a polar shadow-casting approach for performance and watertightness.
        """
        if self.blocker_mask is None:
            return np.zeros((mask_h, mask_w), dtype=np.uint8)

        combined_mask = np.zeros((mask_h, mask_w), dtype=np.uint8)

        # Optimization: Only process unique points and points within mask bounds
        unique_sources = set()
        for x, y in source_points:
            if 0 <= x < mask_w and 0 <= y < mask_h:
                unique_sources.add((x, y))

        for sx, sy in unique_sources:
            # 1. Create a local coordinate system around the source
            # We only need to process up to vision_range_px
            r = vision_range_px
            # Polar warp parameters
            # rows = number of angles, cols = distance
            # 1440 rows for 0.25 degree resolution
            polar_rows = 1440
            polar_cols = r

            # Warp the blocker mask to polar coordinates
            # Use INTER_NEAREST to avoid blurring walls
            polar_blockers = cv2.warpPolar(
                self.blocker_mask,
                (polar_cols, polar_rows),
                (float(sx), float(sy)),
                float(r),
                cv2.WARP_FILL_OUTLIERS + cv2.INTER_NEAREST,
            )

            # 2. In polar space, find the "shadow" of each blocker
            # For each angle (row), find the first non-zero pixel (wall)
            # Everything after that pixel is in shadow.

            # Use argmax to find the first 255 (wall) in each row
            # If no 255 found, it returns 0, but we need to know if it actually found one.
            # So we check if the row has any non-zero pixels.
            has_wall = np.any(polar_blockers > 0, axis=1)
            first_wall = np.argmax(polar_blockers > 0, axis=1)

            # Create a visibility mask in polar space
            # 255 for visible, 0 for shadow
            polar_vision = np.zeros((polar_rows, polar_cols), dtype=np.uint8)
            for row in range(polar_rows):
                if has_wall[row]:
                    polar_vision[row, : first_wall[row]] = 255
                else:
                    polar_vision[row, :] = 255

            # 3. Warp back to Cartesian coordinates
            # Use INTER_NEAREST to avoid blurred edges (light leaks)
            source_vision = cv2.warpPolar(
                polar_vision,
                (mask_w, mask_h),
                (float(sx), float(sy)),
                float(r),
                cv2.WARP_FILL_OUTLIERS + cv2.WARP_INVERSE_MAP + cv2.INTER_NEAREST,
            )

            # 4. Union with combined mask
            cv2.bitwise_or(combined_mask, source_vision, combined_mask)

        return combined_mask

    def get_token_vision_mask(
        self,
        token_id: int,
        origin_x: float,
        origin_y: float,
        size: int,
        vision_range_grid: float,
        mask_width: int,
        mask_height: int,
    ) -> np.ndarray:
        """
        Calculates a unioned LOS mask from the token's center and corners.
        Returns a uint8 mask (0=hidden, 255=visible).
        """
        # 1. Check Mask Cache
        gx = int((origin_x - self.grid_origin[0]) // self.grid_spacing_svg)
        gy = int((origin_y - self.grid_origin[1]) // self.grid_spacing_svg)
        mask_cache_key = (token_id, gx, gy, size)

        if mask_cache_key in self.mask_cache:
            mask = self.mask_cache[mask_cache_key]
            if mask.shape == (mask_height, mask_width):
                return mask

        # 2. Coordinate Conversion
        cx_mask = int(origin_x * self.svg_to_mask_scale)
        cy_mask = int(origin_y * self.svg_to_mask_scale)
        vision_range_px = int(vision_range_grid * 16)  # 16px per grid unit

        # 3. Calculate Token Footprint (Corner Peeking)
        footprint = self._calculate_token_footprint(cx_mask, cy_mask, size)

        # 4. Extract Source Points (Area Light Sources)
        # We use a set of points from the footprint boundary.
        # Find points on the edge of the footprint.
        source_points = []
        if np.any(footprint > 0):
            # For efficiency, we use a subset of points:
            # - Token Center
            source_points.append((cx_mask, cy_mask))

            # - Corners and Midpoints of the footprint's bounding box
            coords = np.where(footprint > 0)
            min_y, max_y = np.min(coords[0]), np.max(coords[0])
            min_x, max_x = np.min(coords[1]), np.max(coords[1])
            mid_y, mid_x = (min_y + max_y) // 2, (min_x + max_x) // 2

            source_points.extend(
                [
                    (min_x, min_y),
                    (max_x, min_y),
                    (min_x, max_y),
                    (max_x, max_y),  # Corners
                    (mid_x, min_y),
                    (mid_x, max_y),
                    (min_x, mid_y),
                    (max_x, mid_y),  # Midpoints
                ]
            )

        # 5. Calculate and Union Polygons (Pixel-based)
        mask = self._calculate_visibility_mask(
            source_points, vision_range_px, mask_width, mask_height
        )

        # 6. Update Cache
        self.mask_cache[mask_cache_key] = mask
        return mask

    def get_aggregate_vision_mask(
        self,
        tokens: List[Token],
        map_config: MapConfigManager,
        mask_width: int,
        mask_height: int,
        vision_range_grid: float = 25.0,
    ) -> Optional[np.ndarray]:
        """
        Calculates a combined vision mask for all PC tokens.
        Useful for 'Sync Vision' actions.
        """
        combined_pc_mask = None

        pc_tokens = [
            t for t in tokens if map_config.resolve_token_profile(t.id).type == "PC"
        ]

        for token in pc_tokens:
            token_mask = self.get_token_vision_mask(
                token.id,
                token.world_x,
                token.world_y,
                size=map_config.resolve_token_profile(token.id).size,
                vision_range_grid=vision_range_grid,
                mask_width=mask_width,
                mask_height=mask_height,
            )
            if combined_pc_mask is None:
                combined_pc_mask = token_mask.copy()
            else:
                cv2.bitwise_or(combined_pc_mask, token_mask, combined_pc_mask)

        return combined_pc_mask
