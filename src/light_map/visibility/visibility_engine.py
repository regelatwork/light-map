from __future__ import annotations
import cv2
import numpy as np
import math
from collections import deque
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING, Set
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker
from light_map.core.common_types import Token, GridType

# Optional Numba support
try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

# Blocker Mask Constants
MASK_VALUE_NONE = 0
MASK_VALUE_WALL = 255
MASK_VALUE_DOOR_CLOSED = 200
MASK_VALUE_DOOR_OPEN = 150
MASK_VALUE_TALL = 100

if TYPE_CHECKING:
    from light_map.core.common_types import Token
    from light_map.map.map_config import MapConfigManager


if HAS_NUMBA:
    @njit(cache=True)
    def _numba_is_line_obstructed(
        x1: int, y1: int, x2: int, y2: int, blocker_mask: np.ndarray,
        viewer_starts_in_tall: bool
    ) -> bool:
        """
        Numba-optimized line obstruction check.
        Checks ALL pixels on the line EXCEPT the target point (x2, y2).
        This allows us to 'see' the blocker itself without being blocked by it.
        
        Tall Object Logic:
        A line is blocked if it transitions from TALL to OPEN, unless it is
        the very first transition (the 'First Exit' rule).
        """
        h, w = blocker_mask.shape
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        num_steps = dx if dx > dy else dy

        if num_steps == 0:
            return False

        has_exited_initial_tall_zone = not viewer_starts_in_tall
        in_tall_zone = viewer_starts_in_tall

        for i in range(num_steps):
            t = i / num_steps
            px = int(round(x1 + t * (x2 - x1)))
            py = int(round(y1 + t * (y2 - y1)))

            if px < 0:
                px = 0
            elif px >= w:
                px = w - 1
            if py < 0:
                py = 0
            elif py >= h:
                py = h - 1

            val = blocker_mask[py, px]
            
            # 1. Standard Blockers (Wall or Closed Door)
            if val == 255 or val == 200: 
                return True
                
            # 2. Tall Object Transitions
            is_currently_tall = (val == 100)
            
            if in_tall_zone and not is_currently_tall:
                # Transition: TALL -> OPEN
                if has_exited_initial_tall_zone:
                    return True # Blocked: Second exit from tall
                has_exited_initial_tall_zone = True
                in_tall_zone = False
            elif not in_tall_zone and is_currently_tall:
                # Transition: OPEN -> TALL
                in_tall_zone = True
                
        return False

    @njit(cache=True)
    def _numba_bfs_flood_fill(
        blocker_mask: np.ndarray,
        blocker_id_map: np.ndarray,
        vis_mask: np.ndarray,
        visited: np.ndarray,
        border_xs: np.ndarray,
        border_ys: np.ndarray,
        vision_range_px: int,
        cx: float,
        cy: float,
        num_blockers: int,
        viewer_starts_in_tall: bool
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Numba-optimized BFS visibility propagation.
        Tracks which blocker IDs were 'discovered' during the fill.
        """
        h, w = blocker_mask.shape
        range_sq = vision_range_px**2
        
        # Track discovered blocker indices
        discovered_indices = np.zeros(num_blockers, dtype=np.uint8)
        
        hint_indices = np.full((h, w), -1, dtype=np.int32)
        queue_x = np.empty(w * h, dtype=np.int32)
        queue_y = np.empty(w * h, dtype=np.int32)
        head = 0
        tail = 0

        for i in range(len(border_xs)):
            bx, by = border_xs[i], border_ys[i]
            queue_x[tail] = bx
            queue_y[tail] = by
            tail += 1
            hint_indices[by, bx] = i

        while head < tail:
            x = queue_x[head]
            y = queue_y[head]
            head += 1

            parent_hint_idx = hint_indices[y, x]

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy

                if nx < 0 or nx >= w or ny < 0 or ny >= h:
                    continue
                
                if visited[ny, nx]:
                    continue

                if (nx - cx) ** 2 + (ny - cy) ** 2 > range_sq:
                    continue

                val = blocker_mask[ny, nx]
                found_hint = -1
                
                if parent_hint_idx != -1:
                    sx = border_xs[parent_hint_idx]
                    sy = border_ys[parent_hint_idx]
                    if not _numba_is_line_obstructed(sx, sy, nx, ny, blocker_mask, viewer_starts_in_tall):
                        found_hint = parent_hint_idx

                if found_hint == -1:
                    for i in range(len(border_xs)):
                        if i == parent_hint_idx:
                            continue
                        sx = border_xs[i]
                        sy = border_ys[i]
                        if not _numba_is_line_obstructed(sx, sy, nx, ny, blocker_mask, viewer_starts_in_tall):
                            found_hint = i
                            break

                if found_hint != -1:
                    visited[ny, nx] = True 
                    vis_mask[ny, nx] = 255
                    
                    if val == 255 or val == 200: # WALL or DOOR_CLOSED
                        bid = blocker_id_map[ny, nx]
                        if bid >= 0:
                            discovered_indices[bid] = 1
                        # Do NOT add blocker to queue; vision stops here
                    else:
                        # Continue flooding floor space OR tall object tops
                        if val == 100: # TALL_OBJECT
                             bid = blocker_id_map[ny, nx]
                             if bid >= 0:
                                 discovered_indices[bid] = 1
                        
                        hint_indices[ny, nx] = found_hint
                        queue_x[tail] = nx
                        queue_y[tail] = ny
                        tail += 1

        return vis_mask, discovered_indices


class VisibilityEngine:
    """
    Calculates visibility masks based on high-resolution blocker grids.
    Ensures watertight walls and supports object-based discovery.
    """

    def __init__(
        self, grid_spacing_svg: float, grid_origin: Tuple[float, float] = (0.0, 0.0)
    ):
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin = grid_origin
        self.blockers: List[VisibilityBlocker] = []

        # Mask Cache: (token_id, grid_x, grid_y, size) -> (vis_mask, discovered_ids)
        self.mask_cache: Dict[Tuple[int, int, int, int], Tuple[np.ndarray, Set[str]]] = {}

        self.blocker_mask: Optional[np.ndarray] = None
        self.blocker_id_map: Optional[np.ndarray] = None
        self.svg_to_mask_scale = 16.0 / grid_spacing_svg

    @property
    def width(self) -> int:
        return self.blocker_mask.shape[1] if self.blocker_mask is not None else 0

    @property
    def height(self) -> int:
        return self.blocker_mask.shape[0] if self.blocker_mask is not None else 0

    def calculate_mask_dimensions(self, svg_w: float, svg_h: float) -> Tuple[int, int]:
        return int(svg_w * self.svg_to_mask_scale), int(svg_h * self.svg_to_mask_scale)

    def update_blockers(
        self,
        blockers: List[VisibilityBlocker],
        mask_width: int = 0,
        mask_height: int = 0,
    ):
        """
        Renders a high-resolution blocker mask and an ID map for discovery.
        """
        self.blockers = blockers
        self.mask_cache = {}

        if mask_width > 0 and mask_height > 0:
            self.blocker_mask = np.zeros((mask_height, mask_width), dtype=np.uint8)
            self.blocker_id_map = np.full((mask_height, mask_width), -1, dtype=np.int32)

        # Priority sorting: TALL_OBJECT (0) -> DOOR (1) -> WALL (2)
        # Opaque walls MUST be rendered last to ensure they aren't overwritten by tall object surfaces.
        priority = {
            VisibilityType.TALL_OBJECT: 0,
            VisibilityType.DOOR: 1,
            VisibilityType.WALL: 2,
        }
        
        # Sort indices of blockers based on their priority
        sorted_indices = sorted(
            range(len(blockers)),
            key=lambda i: priority.get(blockers[i].type, 2)
        )

        for idx in sorted_indices:
            blocker = blockers[idx]
            points = blocker.points
            if len(points) < 2:
                continue

            if self.blocker_mask is not None:
                # Windows are transparent to vision
                if blocker.type != VisibilityType.WINDOW:
                    mask_points = []
                    for px, py in points:
                        mx = int(px * self.svg_to_mask_scale)
                        my = int(py * self.svg_to_mask_scale)
                        mask_points.append((mx, my))

                    if blocker.type == VisibilityType.TALL_OBJECT:
                        # Render filled polygon for tall objects
                        pts = np.array(mask_points, dtype=np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(self.blocker_mask, [pts], MASK_VALUE_TALL)
                        cv2.fillPoly(self.blocker_id_map, [pts], idx)
                    else:
                        for i in range(len(mask_points) - 1):
                            p1 = mask_points[i]
                            p2 = mask_points[i + 1]

                            # Choose pixel value based on blocker type and state
                            if blocker.type == VisibilityType.DOOR:
                                px_val = MASK_VALUE_DOOR_OPEN if blocker.is_open else MASK_VALUE_DOOR_CLOSED
                            else:
                                px_val = MASK_VALUE_WALL

                            # Render collision grid
                            cv2.line(self.blocker_mask, p1, p2, px_val, thickness=2)
                            cv2.circle(self.blocker_mask, p1, 1, px_val, -1)
                            cv2.circle(self.blocker_mask, p2, 1, px_val, -1)

                            # Render ID map
                            cv2.line(self.blocker_id_map, p1, p2, idx, thickness=2)
                            cv2.circle(self.blocker_id_map, p1, 1, idx, -1)
                            cv2.circle(self.blocker_id_map, p2, 1, idx, -1)

    def _calculate_token_footprint_with_planes(
        self,
        cx_mask: int,
        cy_mask: int,
        size: int,
        grid_type: GridType = GridType.SQUARE,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the token's 'light source' footprint.
        Uses BFS constrained by grid cell boundaries (square or hex).
        Returns (footprint_mask, cell_planes).
        """
        if self.blocker_mask is None:
            return np.zeros((1, 1), dtype=np.uint8), np.empty((0, 3), dtype=np.float32)

        h, w = self.blocker_mask.shape
        footprint = np.zeros((h, w), dtype=np.uint8)

        if not (0 <= cx_mask < w and 0 <= cy_mask < h):
            return footprint, np.empty((0, 3), dtype=np.float32)

        # 1. Determine cell boundaries (Planes ax + by + c <= 0)
        cell_planes_list = []
        if grid_type == GridType.SQUARE:
            # Radius in mask space (16 units per grid cell)
            r = (size * 16) // 2
            # 4 Planes: x <= cx+r, x >= cx-r, y <= cy+r, y >= cy-r
            cell_planes_list = [
                [1.0, 0.0, -(cx_mask + r)],
                [-1.0, 0.0, (cx_mask - r)],
                [0.0, 1.0, -(cy_mask + r)],
                [0.0, -1.0, (cy_mask - r)],
            ]
        else:
            # Hex Geometry (Radius in mask space is 16 / sqrt(3) * size)
            spacing = 16.0 * size
            apothem = spacing / 2.0

            if grid_type == GridType.HEX_POINTY:
                # Normals for Pointy Top: (±1, 0), (±0.5, ±sqrt(3)/2)
                s32 = math.sqrt(3) / 2.0
                normals = [
                    (1.0, 0.0),
                    (-1.0, 0.0),
                    (0.5, s32),
                    (0.5, -s32),
                    (-0.5, s32),
                    (-0.5, -s32),
                ]
            else:
                # Normals for Flat Top: (0, ±1), (±sqrt(3)/2, ±0.5)
                s32 = math.sqrt(3) / 2.0
                normals = [
                    (0.0, 1.0),
                    (0.0, -1.0),
                    (s32, 0.5),
                    (s32, -0.5),
                    (-s32, 0.5),
                    (-s32, -0.5),
                ]

            for nx, ny in normals:
                # c = -(nx*cx + ny*cy) - apothem
                c = -(nx * cx_mask + ny * cy_mask) - apothem
                cell_planes_list.append([nx, ny, c])

        cell_planes = np.array(cell_planes_list, dtype=np.float32)

        # 2. BFS Flood Fill within boundaries
        queue = deque([(cy_mask, cx_mask)])
        footprint[cy_mask, cx_mask] = 255

        while queue:
            y, x = queue.popleft()

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx

                if 0 <= nx < w and 0 <= ny < h:
                    if footprint[ny, nx] == 0:
                        # Check Plane boundaries
                        is_inside = True
                        for i in range(cell_planes.shape[0]):
                            if (
                                cell_planes[i, 0] * nx
                                + cell_planes[i, 1] * ny
                                + cell_planes[i, 2]
                                > 0
                            ):
                                is_inside = False
                                break

                        if is_inside:
                            # Standard blocker check for abutting walls
                            # Tokens can stand on empty space or tall objects
                            val = self.blocker_mask[ny, nx]
                            if val == 0 or val == 100:
                                footprint[ny, nx] = 255
                                queue.append((ny, nx))

        return footprint, cell_planes

    def _get_footprint_border_points(self, footprint: np.ndarray) -> List[Tuple[int, int]]:
        """
        Extracts the (x, y) coordinates of all pixels on the inner perimeter of the footprint.
        """
        if footprint is None or not np.any(footprint > 0):
            return []

        kernel = np.ones((3, 3), np.uint8)
        eroded = cv2.erode(footprint, kernel, iterations=1)
        border_mask = cv2.subtract(footprint, eroded)
        y_coords, x_coords = np.where(border_mask > 0)
        return list(zip(x_coords.tolist(), y_coords.tolist()))

    def _is_line_obstructed(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> bool:
        """
        Checks if any pixel on the line between p1 and p2 is a blocker.
        Returns True if a blocker is found at p1 or any point in between EXCEPT p2.
        """
        if self.blocker_mask is None:
            return False

        x1, y1 = p1
        x2, y2 = p2

        if HAS_NUMBA:
            return _numba_is_line_obstructed(x1, y1, x2, y2, self.blocker_mask)

        h, w = self.blocker_mask.shape
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        num_steps = dx if dx > dy else dy

        if num_steps == 0:
            return False

        for i in range(num_steps):
            t = i / num_steps
            px = int(round(x1 + t * (x2 - x1)))
            py = int(round(y1 + t * (y2 - y1)))

            px = max(0, min(px, w - 1))
            py = max(0, min(py, h - 1))

            val = self.blocker_mask[py, px]
            if val == MASK_VALUE_WALL or val == MASK_VALUE_DOOR_CLOSED:
                return True
        return False

    def _find_visible_source(
        self,
        target_p: Tuple[int, int],
        border_points: List[Tuple[int, int]],
        hint_source: Optional[Tuple[int, int]] = None,
    ) -> Optional[Tuple[int, int]]:
        """
        Finds a point in border_points that has LOS to target_p.
        Checks the hint_source first for optimization.
        """
        if hint_source is not None:
            if not self._is_line_obstructed(hint_source, target_p):
                return hint_source

        for source_p in border_points:
            if source_p == hint_source:
                continue
            if not self._is_line_obstructed(source_p, target_p):
                return source_p

        return None

    def _calculate_visibility(
        self,
        footprint: np.ndarray,
        vision_range_px: int,
        mask_w: int,
        mask_h: int,
    ) -> Tuple[np.ndarray, Set[str]]:
        """
        Calculates visibility using a BFS constrained by Line-of-Sight.
        Returns (vision_mask, discovered_ids).
        """
        if self.blocker_mask is None:
            return np.zeros((mask_h, mask_w), dtype=np.uint8), set()

        vis_mask = footprint.copy()
        visited = footprint > 0

        border_points = self._get_footprint_border_points(footprint)
        if not border_points:
            return vis_mask, set()

        coords = np.where(footprint > 0)
        cx = np.mean(coords[1])
        cy = np.mean(coords[0])
        
        # Determine if the viewer is currently in a TALL zone
        # We check the center of the footprint
        viewer_starts_in_tall = False
        if 0 <= int(cx) < mask_w and 0 <= int(cy) < mask_h:
            if self.blocker_mask[int(cy), int(cx)] == 100:
                viewer_starts_in_tall = True

        if HAS_NUMBA:
            border_xs = np.array([p[0] for p in border_points], dtype=np.int32)
            border_ys = np.array([p[1] for p in border_points], dtype=np.int32)
            v_mask, disc_indices = _numba_bfs_flood_fill(
                self.blocker_mask, self.blocker_id_map, vis_mask, visited,
                border_xs, border_ys,
                vision_range_px, cx, cy, len(self.blockers),
                viewer_starts_in_tall
            )
            # Map indices back to IDs for doors/tall objects
            discovered_ids = {
                self.blockers[i].id 
                for i in np.where(disc_indices > 0)[0] 
                if self.blockers[i].type in (VisibilityType.DOOR, VisibilityType.TALL_OBJECT)
            }
            return v_mask, discovered_ids

        # Python Fallback (Simplified propagation for brevity)
        discovered_ids = set()
        queue = deque(border_points)
        hint_xs = np.full((mask_h, mask_w), -1, dtype=np.int16)
        hint_ys = np.full((mask_h, mask_w), -1, dtype=np.int16)
        for x, y in border_points:
            hint_xs[y, x], hint_ys[y, x] = x, y

        range_sq = vision_range_px**2

        while queue:
            x, y = queue.popleft()
            hx, hy = hint_xs[y, x], hint_ys[y, x]
            hint = (int(hx), int(hy)) if hx != -1 else None

            for nx, ny in [(x, y+1), (x, y-1), (x+1, y), (x-1, y)]:
                if 0 <= nx < mask_w and 0 <= ny < mask_h and not visited[ny, nx]:
                    if (nx - cx) ** 2 + (ny - cy) ** 2 <= range_sq:
                        # Note: _is_line_obstructed would also need update for Python fallback
                        # but we prioritize Numba path as instructed.
                        found_source = self._find_visible_source((nx, ny), border_points, hint)
                        if found_source:
                            visited[ny, nx] = True
                            vis_mask[ny, nx] = 255
                            val = self.blocker_mask[ny, nx]
                            if val > 0: # Blocker
                                bid = self.blocker_id_map[ny, nx]
                                if bid >= 0:
                                    bt = self.blockers[bid].type
                                    if bt in (VisibilityType.DOOR, VisibilityType.TALL_OBJECT):
                                        discovered_ids.add(self.blockers[bid].id)
                                    
                                    if val == 255 or val == 200: # STOP for wall/door
                                        continue
                            
                            # Continue flooding for floor or tall object tops
                            hint_xs[ny, nx], hint_ys[ny, nx] = found_source
                            queue.append((nx, ny))

        return vis_mask, discovered_ids

    def get_token_vision_mask(
        self,
        token_id: int,
        origin_x: float,
        origin_y: float,
        size: int,
        vision_range_grid: float,
        mask_width: int,
        mask_height: int,
        grid_type: GridType = GridType.SQUARE,
    ) -> Tuple[np.ndarray, Set[str]]:
        """
        Calculates a unioned LOS mask and discovered door IDs.
        """
        gx = int((origin_x - self.grid_origin[0]) // self.grid_spacing_svg)
        gy = int((origin_y - self.grid_origin[1]) // self.grid_spacing_svg)
        mask_cache_key = (token_id, gx, gy, size, grid_type)

        if mask_cache_key in self.mask_cache:
            return self.mask_cache[mask_cache_key]

        cx_mask = int(origin_x * self.svg_to_mask_scale)
        cy_mask = int(origin_y * self.svg_to_mask_scale)
        vision_range_px = int(vision_range_grid * 16)

        footprint, cell_planes = self._calculate_token_footprint_with_planes(cx_mask, cy_mask, size, grid_type)
        result = self._calculate_visibility(
            footprint, vision_range_px, mask_width, mask_height
        )

        self.mask_cache[mask_cache_key] = result
        return result

    def get_aggregate_vision_mask(
        self,
        tokens: List[Token],
        map_config: MapConfigManager,
        mask_width: int,
        mask_height: int,
        vision_range_grid: float = 25.0,
        grid_type: GridType = GridType.SQUARE,
    ) -> Tuple[Optional[np.ndarray], Set[str]]:
        """
        Calculates combined vision mask and set of discovered door IDs for all PC tokens.
        """
        combined_pc_mask = None
        all_discovered_ids = set()

        pc_tokens = [
            t for t in tokens if map_config.resolve_token_profile(t.id).type == "PC"
        ]

        for token in pc_tokens:
            token_mask, discovered_ids = self.get_token_vision_mask(
                token.id,
                token.world_x,
                token.world_y,
                size=map_config.resolve_token_profile(token.id).size,
                vision_range_grid=vision_range_grid,
                mask_width=mask_width,
                mask_height=mask_height,
                grid_type=grid_type,
            )
            if combined_pc_mask is None:
                combined_pc_mask = token_mask.copy()
            else:
                cv2.bitwise_or(combined_pc_mask, token_mask, combined_pc_mask)
            
            all_discovered_ids.update(discovered_ids)

        return combined_pc_mask, all_discovered_ids
