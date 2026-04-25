from __future__ import annotations
import cv2
import numpy as np
import math
from collections import deque
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING, Set
from light_map.visibility.visibility_types import VisibilityType, VisibilityBlocker
from light_map.core.common_types import Token, GridType, CoverResult, WedgeSegment

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
MASK_VALUE_LOW = 50

if TYPE_CHECKING:
    from light_map.core.common_types import Token
    from light_map.map.map_config import MapConfigManager


if HAS_NUMBA:

    @njit(cache=True)
    def _numba_trace_path(
        x1: int, y1: int, x2: int, y2: int, blocker_mask: np.ndarray
    ) -> int:
        """
        Traces a path from Target (x1, y1) to Attacker (x2, y2).
        Returns:
            0: Clear
            1: Blocked (Wall/Door)
            2: Obscured (Low Object meeting Starfinder 1e conditions)
        """
        h, w = blocker_mask.shape
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        total_dist = math.sqrt(dx * dx + dy * dy)
        num_steps = int(max(dx, dy))

        if num_steps == 0:
            return 0

        result = 0
        for i in range(num_steps + 1):
            t = i / num_steps
            px = int(round(x1 + t * (x2 - x1)))
            py = int(round(y1 + t * (y2 - y1)))

            if px < 0 or px >= w or py < 0 or py >= h:
                continue

            val = blocker_mask[py, px]
            if val == 255 or val == 200:  # WALL or DOOR_CLOSED
                return 1
            if val == 50:  # LOW_OBJECT
                # Starfinder 1e: Target within 30' (96px) AND closer than attacker
                dist_to_obj = math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
                if dist_to_obj <= 96.0 and dist_to_obj < (total_dist / 2.0):
                    # Flag that we found an obscuring object, but CONTINUE tracing
                    # to check for walls later in the line.
                    result = 2

        return result

    @njit(cache=True)
    def _numba_calculate_cover_grade(
        npc_pixels: np.ndarray, pc_pixels: np.ndarray, blocker_mask: np.ndarray
    ) -> Tuple[float, float, int]:
        """
        Calculates:
        1. total_ratio: percentage of NPC boundary pixels obscured (Wall or Low).
        2. wall_ratio: percentage of NPC boundary pixels blocked by WALLS/DOORS.
        3. best_apex_index: index of the PC corner that provided the best view.
        Starfinder 1e: Attacker chooses ONE corner that sees as much as possible.
        """
        num_npc = len(npc_pixels)
        num_pc = len(pc_pixels)
        if num_npc == 0 or num_pc == 0:
            return 0.0, 0.0, 0

        min_total_ratio = 1.1
        min_wall_ratio = 1.1
        found_any_loe = False
        
        best_indices = np.zeros(num_pc, dtype=np.int32)
        best_count = 0

        # For each Attacker corner
        for j in range(num_pc):
            px, py = pc_pixels[j, 0], pc_pixels[j, 1]

            obscured_count = 0
            wall_count = 0
            has_any_loe_from_this_corner = False

            for i in range(num_npc):
                nx, ny = npc_pixels[i, 0], npc_pixels[i, 1]
                status = _numba_trace_path(nx, ny, px, py, blocker_mask)

                # status: 0=Clear, 1=Blocked(Wall), 2=Obscured(Low)
                if status != 0:
                    obscured_count += 1
                    if status == 1:
                        wall_count += 1

                if status != 1:  # Clear or Low Object both allow Line of Effect
                    has_any_loe_from_this_corner = True

            if has_any_loe_from_this_corner:
                found_any_loe = True
                total_ratio = obscured_count / num_npc
                wall_ratio = wall_count / num_npc

                # Selection Logic:
                # We want the corner that has the best view (lowest wall ratio).
                # If wall ratios are equal, choose the one with less total obstruction.
                if wall_ratio < min_wall_ratio or (
                    wall_ratio == min_wall_ratio and total_ratio < min_total_ratio
                ):
                    min_wall_ratio = wall_ratio
                    min_total_ratio = total_ratio
                    best_indices[0] = j
                    best_count = 1
                elif wall_ratio == min_wall_ratio and total_ratio == min_total_ratio:
                    best_indices[best_count] = j
                    best_count += 1

        if not found_any_loe:
            return -1.0, -1.0, 0

        best_index = best_indices[best_count // 2]
        return min_total_ratio, min_wall_ratio, best_index

    @njit(cache=True)
    def _numba_is_line_obstructed(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        blocker_mask: np.ndarray,
        viewer_starts_in_tall: bool,
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
            is_currently_tall = val == 100

            if in_tall_zone and not is_currently_tall:
                # Transition: TALL -> OPEN
                if has_exited_initial_tall_zone:
                    return True  # Blocked: Second exit from tall
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
        viewer_starts_in_tall: bool,
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
                    if not _numba_is_line_obstructed(
                        sx, sy, nx, ny, blocker_mask, viewer_starts_in_tall
                    ):
                        found_hint = parent_hint_idx

                if found_hint == -1:
                    for i in range(len(border_xs)):
                        if i == parent_hint_idx:
                            continue
                        sx = border_xs[i]
                        sy = border_ys[i]
                        if not _numba_is_line_obstructed(
                            sx, sy, nx, ny, blocker_mask, viewer_starts_in_tall
                        ):
                            found_hint = i
                            break

                if found_hint != -1:
                    visited[ny, nx] = True
                    vis_mask[ny, nx] = 255

                    if val == 255 or val == 200:  # WALL or DOOR_CLOSED
                        bid = blocker_id_map[ny, nx]
                        if bid >= 0:
                            discovered_indices[bid] = 1
                        # Do NOT add blocker to queue; vision stops here
                    else:
                        # Continue flooding floor space OR tall object tops OR open doors
                        if val == 100 or val == 150:  # TALL_OBJECT or DOOR_OPEN
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
        self.mask_cache: Dict[
            Tuple[int, int, int, int], Tuple[np.ndarray, Set[str]]
        ] = {}

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

        # Priority sorting: LOW_OBJECT (0) -> TALL_OBJECT (1) -> DOOR (2) -> WALL (3)
        # Opaque walls MUST be rendered last to ensure they aren't overwritten by tall object surfaces.
        priority = {
            VisibilityType.LOW_OBJECT: 0,
            VisibilityType.TALL_OBJECT: 1,
            VisibilityType.DOOR: 2,
            VisibilityType.WALL: 3,
        }

        # Sort indices of blockers based on their priority
        sorted_indices = sorted(
            range(len(blockers)), key=lambda i: priority.get(blockers[i].type, 3)
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

                    if blocker.type in (
                        VisibilityType.TALL_OBJECT,
                        VisibilityType.LOW_OBJECT,
                    ):
                        # Render filled polygon for tall and low objects
                        pts = np.array(mask_points, dtype=np.int32).reshape((-1, 1, 2))
                        val = (
                            MASK_VALUE_TALL
                            if blocker.type == VisibilityType.TALL_OBJECT
                            else MASK_VALUE_LOW
                        )
                        cv2.fillPoly(self.blocker_mask, [pts], val)
                        cv2.fillPoly(self.blocker_id_map, [pts], idx)
                    else:
                        for i in range(len(mask_points) - 1):
                            p1 = mask_points[i]
                            p2 = mask_points[i + 1]

                            # Choose pixel value based on blocker type and state
                            if blocker.type == VisibilityType.DOOR:
                                px_val = (
                                    MASK_VALUE_DOOR_OPEN
                                    if blocker.is_open
                                    else MASK_VALUE_DOOR_CLOSED
                                )
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
        ignore_blockers: bool = False,
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
        visited = np.zeros((h, w), dtype=bool)
        visited[cy_mask, cx_mask] = True
        footprint[cy_mask, cx_mask] = 255

        while queue:
            y, x = queue.popleft()

            for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ny, nx = y + dy, x + dx

                if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                    visited[ny, nx] = True

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
                        if ignore_blockers:
                            footprint[ny, nx] = 255
                            queue.append((ny, nx))
                        else:
                            # Standard blocker check for abutting walls
                            # Tokens can stand on empty space or tall objects
                            val = self.blocker_mask[ny, nx]
                            if val == 0 or val == 100:
                                footprint[ny, nx] = 255
                                queue.append((ny, nx))

        return footprint, cell_planes

    def _get_footprint_border_points(
        self, footprint: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Extracts the (x, y) coordinates of all pixels on the perimeter of the footprint.
        Uses cv2.findContours to ensure they are returned in a spatially ordered path.
        """
        if footprint is None or not np.any(footprint > 0):
            return []

        # Find external contour
        contours, _ = cv2.findContours(
            footprint, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        if not contours:
            return []

        # Pick the largest contour (the token itself)
        main_contour = max(contours, key=cv2.contourArea)
        
        # Reshape (N, 1, 2) to (N, 2)
        points = main_contour.reshape((-1, 2))
        return [(int(p[0]), int(p[1])) for p in points]

    def _get_token_boundary_pixels(self, token: Token) -> np.ndarray:
        """
        Helper to get boundary pixels of a token in mask space.
        Returns Nx2 int32 array for Numba.
        """
        cx_mask = int(token.world_x * self.svg_to_mask_scale)
        cy_mask = int(token.world_y * self.svg_to_mask_scale)
        # Use token's profile size if available, default to 1 (Medium)
        size = token.size if token.size is not None else 1

        # Grid type default to SQUARE for cover logic
        # ignore_blockers=True ensures we get the FULL footprint even if part is behind a wall
        footprint, _ = self._calculate_token_footprint_with_planes(
            cx_mask, cy_mask, size, GridType.SQUARE, ignore_blockers=True
        )
        border_points = self._get_footprint_border_points(footprint)

        if not border_points:
            return np.empty((0, 2), dtype=np.int32)

        return np.array(border_points, dtype=np.int32)

    def calculate_token_cover_bonuses(
        self, source_token: Token, target_token: Token
    ) -> CoverResult:
        """
        Calculates AC and Reflex save bonuses for a target token viewed from a source token.
        Returns CoverResult containing bonuses, best apex, and visual segments.
        """
        if self.blocker_mask is None:
            return CoverResult(0, 0, (0, 0), [], np.empty((0, 2), dtype=np.int32))

        # 1. Get boundary pixels
        npc_pixels = self._get_token_boundary_pixels(target_token)
        pc_pixels = self._get_token_boundary_pixels(source_token)

        if len(npc_pixels) == 0 or len(pc_pixels) == 0:
            return CoverResult(0, 0, (0, 0), [], np.empty((0, 2), dtype=np.int32))

        # 2. Use Numba-optimized cover grade calculation
        if HAS_NUMBA:
            total_ratio, wall_ratio, best_apex_idx = _numba_calculate_cover_grade(
                npc_pixels, pc_pixels, self.blocker_mask
            )
        else:
            # Python fallback (not implemented for N^2, returns no cover)
            return CoverResult(0, 0, (0, 0), [], np.empty((0, 2), dtype=np.int32))

        # 3. Map cover grade to Starfinder 1e bonuses
        # Ratio -1.0 means Total Cover (No Line of Effect)
        ac_bonus, reflex_bonus = 0, 0
        if total_ratio < 0:
            ac_bonus, reflex_bonus = -1, -1
        elif wall_ratio >= 0.90:
            ac_bonus, reflex_bonus = 8, 4
        elif total_ratio >= 0.20:
            ac_bonus, reflex_bonus = 4, 2
        elif total_ratio > 0.0:
            ac_bonus, reflex_bonus = 2, 1

        best_apex = (int(pc_pixels[best_apex_idx, 0]), int(pc_pixels[best_apex_idx, 1]))

        # --- SEGMENT EXTRACTION ---
        # Note: npc_pixels is already spatially ordered by _get_footprint_border_points (via findContours)
        segments = []
        if ac_bonus != -1:
            # Trace paths from best apex to sorted NPC pixels
            statuses = []
            target_center = (
                int(target_token.world_x * self.svg_to_mask_scale),
                int(target_token.world_y * self.svg_to_mask_scale),
            )
            for i in range(len(npc_pixels)):
                nx, ny = npc_pixels[i, 0], npc_pixels[i, 1]

                # Near-Side Filtering: (P_x - C_x)*(P_x - A_x) + (P_y - C_y)*(P_y - A_y) <= 0
                # P = (nx, ny), C = target_center, A = best_apex
                near_side = (nx - target_center[0]) * (nx - best_apex[0]) + (
                    ny - target_center[1]
                ) * (ny - best_apex[1])

                if near_side <= 0:
                    status = _numba_trace_path(
                        nx, ny, best_apex[0], best_apex[1], self.blocker_mask
                    )
                    statuses.append(status)
                else:
                    statuses.append(-1)  # Filtered out (Far side)

            # Group contiguous statuses (0: Clear, 2: Obscured)
            current_start = -1
            current_status = -1

            for i in range(len(statuses)):
                status = statuses[i]

                if status in (0, 2):
                    if current_status == -1:
                        current_start = i
                        current_status = status
                    elif status != current_status:
                        # Close previous segment
                        segments.append(
                            WedgeSegment(current_start, i - 1, current_status)
                        )
                        current_start = i
                        current_status = status
                else:
                    # Filtered or Blocked
                    if current_status != -1:
                        segments.append(
                            WedgeSegment(current_start, i - 1, current_status)
                        )
                        current_start = -1
                        current_status = -1

            # Close final segment
            if current_status != -1:
                segments.append(
                    WedgeSegment(current_start, len(statuses) - 1, current_status)
                )

        return CoverResult(
            ac_bonus=ac_bonus,
            reflex_bonus=reflex_bonus,
            best_apex=best_apex,
            segments=segments,
            npc_pixels=npc_pixels,
        )

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
        viewer_starts_in_tall = False
        if 0 <= int(cx) < mask_w and 0 <= int(cy) < mask_h:
            if self.blocker_mask[int(cy), int(cx)] == 100:
                viewer_starts_in_tall = True

        if HAS_NUMBA:
            border_xs = np.array([p[0] for p in border_points], dtype=np.int32)
            border_ys = np.array([p[1] for p in border_points], dtype=np.int32)
            v_mask, disc_indices = _numba_bfs_flood_fill(
                self.blocker_mask,
                self.blocker_id_map,
                vis_mask,
                visited,
                border_xs,
                border_ys,
                vision_range_px,
                cx,
                cy,
                len(self.blockers),
                viewer_starts_in_tall,
            )
            # Map indices back to IDs for doors/tall objects
            discovered_ids = {
                self.blockers[i].id
                for i in np.where(disc_indices > 0)[0]
                if self.blockers[i].type
                in (VisibilityType.DOOR, VisibilityType.TALL_OBJECT)
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

            for nx, ny in [(x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)]:
                if 0 <= nx < mask_w and 0 <= ny < mask_h and not visited[ny, nx]:
                    if (nx - cx) ** 2 + (ny - cy) ** 2 <= range_sq:
                        found_source = self._find_visible_source(
                            (nx, ny), border_points, hint
                        )
                        if found_source:
                            visited[ny, nx] = True
                            vis_mask[ny, nx] = 255
                            val = self.blocker_mask[ny, nx]
                            if val > 0:  # Blocker
                                bid = self.blocker_id_map[ny, nx]
                                if bid >= 0:
                                    bt = self.blockers[bid].type
                                    if bt in (
                                        VisibilityType.DOOR,
                                        VisibilityType.TALL_OBJECT,
                                    ):
                                        discovered_ids.add(self.blockers[bid].id)

                                    if val == 255 or val == 200:  # STOP for wall/door
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

        footprint, cell_planes = self._calculate_token_footprint_with_planes(
            cx_mask, cy_mask, size, grid_type
        )
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
