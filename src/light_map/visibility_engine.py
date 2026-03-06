import math
import cv2
import numpy as np
from typing import List, Tuple, Dict, Optional
from .visibility_types import VisibilityType, VisibilityBlocker


class VisibilityEngine:
    """
    Calculates visibility polygons (LOS) based on SVG-extracted blockers.
    Uses spatial hashing for performance and jitter-resistant caching.
    """

    def __init__(
        self, grid_spacing_svg: float, grid_origin: Tuple[float, float] = (0.0, 0.0)
    ):
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin = grid_origin
        self.blockers: List[VisibilityBlocker] = []
        self.segments: List[
            Tuple[Tuple[float, float], Tuple[float, float], VisibilityBlocker]
        ] = []

        # Spatial Hash: (tile_x, tile_y) -> List[SegmentIndex]
        # Tile size is 10x10 grid cells
        self.tile_size = grid_spacing_svg * 10
        self.spatial_hash: Dict[Tuple[int, int], List[int]] = {}

        # Visibility Cache: (token_id, grid_x, grid_y) -> List[Point]
        self.cache: Dict[Tuple[int, int, int], List[Tuple[float, float]]] = {}

        # Mask Cache: (token_id, grid_x, grid_y, size) -> np.ndarray
        self.mask_cache: Dict[Tuple[int, int, int, int], np.ndarray] = {}

        # Track version of geometry to invalidate cache if doors open/close
        self.geometry_version = 0

        self.blocker_mask: Optional[np.ndarray] = None
        self.svg_to_mask_scale = 16.0 / grid_spacing_svg

    def update_blockers(
        self, blockers: List[VisibilityBlocker], mask_width: int = 0, mask_height: int = 0
    ):
        """
        Rebuilds the spatial hash and segment list.
        Also renders a high-resolution blocker mask if dimensions are provided.
        """
        self.blockers = blockers
        self.segments = []
        self.spatial_hash = {}
        self.cache = {}
        self.mask_cache = {}
        self.geometry_version += 1

        if mask_width > 0 and mask_height > 0:
            self.blocker_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)

        for b_idx, blocker in enumerate(blockers):
            # Convert flattened segments into pairs of points
            points = blocker.segments
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

            for i in range(len(points) - 1):
                p1 = points[i]
                p2 = points[i + 1]
                seg_idx = len(self.segments)
                self.segments.append((p1, p2, blocker))

                # Add to spatial hash
                min_x = min(p1[0], p2[0])
                max_x = max(p1[0], p2[0])
                min_y = min(p1[1], p2[1])
                max_y = max(p1[1], p2[1])

                start_tile_x = int(min_x // self.tile_size)
                end_tile_x = int(max_x // self.tile_size)
                start_tile_y = int(min_y // self.tile_size)
                end_tile_y = int(max_y // self.tile_size)

                for tx in range(start_tile_x, end_tile_x + 1):
                    for ty in range(start_tile_y, end_tile_y + 1):
                        if (tx, ty) not in self.spatial_hash:
                            self.spatial_hash[(tx, ty)] = []
                        self.spatial_hash[(tx, ty)].append(seg_idx)

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
                        if abs(nx - cx_mask) <= range_limit and abs(ny - cy_mask) <= range_limit:
                            # Check if not a wall
                            if self.blocker_mask[ny, nx] == 0:
                                footprint[ny, nx] = 255
                                queue.append((ny, nx))

        return footprint

    def _get_relevant_segments(
        self, origin: Tuple[float, float], radius: float
    ) -> List[int]:
        """
        Uses spatial hash to find segment indices near the origin.
        """
        min_x = origin[0] - radius
        max_x = origin[0] + radius
        min_y = origin[1] - radius
        max_y = origin[1] + radius

        start_tile_x = int(min_x // self.tile_size)
        end_tile_x = int(max_x // self.tile_size)
        start_tile_y = int(min_y // self.tile_size)
        end_tile_y = int(max_y // self.tile_size)

        relevant_indices = set()
        for tx in range(start_tile_x, end_tile_x + 1):
            for ty in range(start_tile_y, end_tile_y + 1):
                if (tx, ty) in self.spatial_hash:
                    relevant_indices.update(self.spatial_hash[(tx, ty)])

        return list(relevant_indices)

    def calculate_visibility(
        self,
        origin: Tuple[float, float],
        vision_range: float,
        token_id: Optional[int] = None,
    ) -> List[Tuple[float, float]]:
        """
        Calculates the visibility polygon from the origin.
        Checks cache first if token_id is provided.
        """
        if token_id is not None:
            # Jitter-resistant cache key
            gx = int((origin[0] - self.grid_origin[0]) // self.grid_spacing_svg)
            gy = int((origin[1] - self.grid_origin[1]) // self.grid_spacing_svg)
            cache_key = (token_id, gx, gy)

            if cache_key in self.cache:
                return self.cache[cache_key]

        # 1. Get relevant segments
        indices = self._get_relevant_segments(origin, vision_range)
        # Filter out segments that are "open" or transparent
        active_segments = []
        for idx in indices:
            p1, p2, blocker = self.segments[idx]
            # Doors only block when NOT open.
            # Windows are currently treated as blocking vision too (as per design for visibility).
            # Actually, design said "Windows: transparent but movement blocking".
            # Wait, design says: "Windows: layers containing 'window'. Vision transparent, movement blocking."
            # "Unbreakable Windows: ... treated as special blockers."
            # Let's clarify: Standard windows ARE transparent to vision.
            # Unbreakable windows also transparent to vision? No, design says:
            # "Unbreakable Windows: ... Vision transparent, movement blocking."
            # Actually, if windows are transparent, they don't block LOS.

            if blocker.type == VisibilityType.DOOR and blocker.is_open:
                continue
            if blocker.type == VisibilityType.WINDOW:
                continue

            active_segments.append((p1, p2))

        # 2. Add bounding circle segments (approximated)
        # For simplicity in this step, let's cast rays at segment endpoints.
        angles = set()
        # Include enough samples for a smooth circle in empty areas
        for i in range(64):
            angles.add((2 * math.pi * i) / 64)

        for p1, p2 in active_segments:
            for p in (p1, p2):
                angle = math.atan2(p[1] - origin[1], p[0] - origin[0])
                angles.add(angle)
                angles.add(angle - 0.00001)
                angles.add(angle + 0.00001)

        # 3. Cast Rays
        sorted_angles = sorted(list(angles))
        polygon = []

        for angle in sorted_angles:
            # Ray direction
            dx = math.cos(angle)
            dy = math.sin(angle)

            # Find closest intersection
            min_t = vision_range

            for p1, p2 in active_segments:
                # Intersection logic (more robust)
                # Ray: r_o + t * r_d
                # Segment: s_p + u * s_d
                s_p = p1
                s_d = (p2[0] - p1[0], p2[1] - p1[1])
                r_o = origin
                r_d = (dx, dy)

                # Solve: r_o + t * r_d = s_p + u * s_d
                # t * r_d - u * s_d = s_p - r_o
                # [r_d_x  -s_d_x] [t] = [s_p_x - r_o_x]
                # [r_d_y  -s_d_y] [u] = [s_p_y - r_o_y]

                det = -r_d[0] * s_d[1] + r_d[1] * s_d[0]
                if abs(det) < 1e-9:
                    continue

                dx_p = s_p[0] - r_o[0]
                dy_p = s_p[1] - r_o[1]

                t = (-s_d[1] * dx_p + s_d[0] * dy_p) / det
                u = (-r_d[1] * dx_p + r_d[0] * dy_p) / det

                if t > 0 and 0 <= u <= 1:
                    if t < min_t:
                        min_t = t

            polygon.append((origin[0] + min_t * dx, origin[1] + min_t * dy))

        # 4. Update cache before returning
        if token_id is not None:
            self.cache[cache_key] = polygon

        return polygon

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
            
            source_points.extend([
                (min_x, min_y), (max_x, min_y), (min_x, max_y), (max_x, max_y), # Corners
                (mid_x, min_y), (mid_x, max_y), (min_x, mid_y), (max_x, mid_y)  # Midpoints
            ])

        # 5. Calculate and Union Polygons (Pixel-based)
        mask = self._calculate_visibility_mask(
            source_points, vision_range_px, mask_width, mask_height
        )

        # 6. Update Cache
        self.mask_cache[mask_cache_key] = mask
        return mask
