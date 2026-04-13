from __future__ import annotations
import cv2
import numpy as np
from collections import deque
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

    def _get_footprint_border_points(self, footprint: np.ndarray) -> List[Tuple[int, int]]:
        """
        Extracts the (x, y) coordinates of all pixels on the inner perimeter of the footprint.
        """
        if footprint is None or not np.any(footprint > 0):
            return []

        # 1. Create a 3x3 connectivity kernel
        kernel = np.ones((3, 3), np.uint8)

        # 2. Erode the footprint by 1 pixel.
        # This removes the outermost layer of pixels.
        eroded = cv2.erode(footprint, kernel, iterations=1)

        # 3. Subtract the eroded version from the original.
        # The result is only the pixels that were on the boundary.
        border_mask = cv2.subtract(footprint, eroded)

        # 4. Extract coordinates.
        y_coords, x_coords = np.where(border_mask > 0)

        # 5. Return as a list of (x, y) tuples
        return list(zip(x_coords.tolist(), y_coords.tolist()))

    def _is_line_obstructed(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """
        Checks if any pixel on the line between p1 and p2 is a blocker.
        Returns True if a blocker is found at p1, p2, or any point in between.
        """
        if self.blocker_mask is None:
            return False

        x1, y1 = p1
        x2, y2 = p2
        h, w = self.blocker_mask.shape

        # Use maximum distance to ensure we sample every pixel along the path
        num_steps = max(abs(x2 - x1), abs(y2 - y1))

        if num_steps == 0:
            if 0 <= x1 < w and 0 <= y1 < h:
                return self.blocker_mask[y1, x1] > 0
            return False

        # Generate integer coordinates along the line
        xs = np.linspace(x1, x2, num_steps + 1).round().astype(int)
        ys = np.linspace(y1, y2, num_steps + 1).round().astype(int)

        # Safety clip to mask boundaries
        xs = np.clip(xs, 0, w - 1)
        ys = np.clip(ys, 0, h - 1)

        # Check for any non-zero (blocker) values in the mask
        return np.any(self.blocker_mask[ys, xs] > 0)

    def _get_neighbors(self, p: Tuple[int, int], mask_w: int, mask_h: int) -> List[Tuple[int, int]]:
        """Returns valid 4-connected neighbors within mask bounds."""
        x, y = p
        neighbors = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < mask_w and 0 <= ny < mask_h:
                neighbors.append((nx, ny))
        return neighbors

    def _find_visible_source(
        self,
        target_p: Tuple[int, int],
        border_points: List[Tuple[int, int]],
        hint_source: Optional[Tuple[int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Finds a point in border_points that has LOS to target_p.
        Checks the hint_source first for optimization (temporal/spatial locality).
        """
        # 1. Check the hint first (most likely to succeed in a flood fill)
        if hint_source is not None:
            if not self._is_line_obstructed(hint_source, target_p):
                return hint_source

        # 2. Check the rest of the border points
        for source_p in border_points:
            if source_p == hint_source:
                continue
            if not self._is_line_obstructed(source_p, target_p):
                return source_p

        return None

    def _calculate_visibility_mask(
        self,
        footprint: np.ndarray,
        vision_range_px: int,
        mask_w: int,
        mask_h: int,
    ) -> np.ndarray:
        """
        Calculates visibility using a BFS (flood fill) constrained by Line-of-Sight.
        Every pixel reached must have LOS to at least one point on the footprint border.
        """
        if self.blocker_mask is None:
            return np.zeros((mask_h, mask_w), dtype=np.uint8)

        # 1. Initialize visibility mask and visited tracker
        vis_mask = footprint.copy()
        visited = footprint > 0

        # 2. Get the starting frontier (border of the footprint)
        border_points = self._get_footprint_border_points(footprint)
        if not border_points:
            return vis_mask

        # 3. Queue for BFS: (x, y)
        queue = deque(border_points)

        # 4. Source hints for optimization (which border point saw which pixel)
        # Using -1 to indicate no hint
        hint_xs = np.full((mask_h, mask_w), -1, dtype=np.int16)
        hint_ys = np.full((mask_h, mask_w), -1, dtype=np.int16)
        for x, y in border_points:
            hint_xs[y, x] = x
            hint_ys[y, x] = y

        # Find footprint center for global range limiting
        coords = np.where(footprint > 0)
        cx = np.mean(coords[1])
        cy = np.mean(coords[0])
        range_sq = vision_range_px**2

        while queue:
            x, y = queue.popleft()

            # Current source point hint
            hx, hy = hint_xs[y, x], hint_ys[y, x]
            hint = (int(hx), int(hy)) if hx != -1 else None

            # Explore neighbors
            for nx, ny in self._get_neighbors((x, y), mask_w, mask_h):
                if visited[ny, nx] or self.blocker_mask[ny, nx] > 0:
                    continue

                # Circular range check
                if (nx - cx) ** 2 + (ny - cy) ** 2 > range_sq:
                    continue

                # Line-of-Sight check against ANY point on the border
                # (Optimized by checking the parent's hint first)
                found_source = self._find_visible_source((nx, ny), border_points, hint)

                if found_source:
                    vis_mask[ny, nx] = 255
                    visited[ny, nx] = True
                    hint_xs[ny, nx], hint_ys[ny, nx] = found_source
                    queue.append((nx, ny))

        return vis_mask

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

        # 4. Calculate Visibility Mask using Flood Fill
        mask = self._calculate_visibility_mask(
            footprint, vision_range_px, mask_width, mask_height
        )

        # 5. Update Cache
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
