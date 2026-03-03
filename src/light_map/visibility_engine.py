import math
import logging
from typing import List, Tuple, Dict, Optional
from .visibility_types import VisibilityType, VisibilityBlocker


class VisibilityEngine:
    """
    Calculates visibility polygons (LOS) based on SVG-extracted blockers.
    Uses spatial hashing for performance and jitter-resistant caching.
    """

    def __init__(self, grid_spacing_svg: float, grid_origin: Tuple[float, float] = (0.0, 0.0)):
        self.grid_spacing_svg = grid_spacing_svg
        self.grid_origin = grid_origin
        self.blockers: List[VisibilityBlocker] = []
        self.segments: List[Tuple[Tuple[float, float], Tuple[float, float], VisibilityBlocker]] = []
        
        # Spatial Hash: (tile_x, tile_y) -> List[SegmentIndex]
        # Tile size is 10x10 grid cells
        self.tile_size = grid_spacing_svg * 10
        self.spatial_hash: Dict[Tuple[int, int], List[int]] = {}
        
        # Visibility Cache: (token_id, grid_x, grid_y) -> List[Point]
        self.cache: Dict[Tuple[int, int, int], List[Tuple[float, float]]] = {}
        
        # Track version of geometry to invalidate cache if doors open/close
        self.geometry_version = 0

    def update_blockers(self, blockers: List[VisibilityBlocker]):
        """
        Rebuilds the spatial hash and segment list.
        """
        self.blockers = blockers
        self.segments = []
        self.spatial_hash = {}
        self.cache = {}
        self.geometry_version += 1

        for b_idx, blocker in enumerate(blockers):
            # Convert flattened segments into pairs of points
            points = blocker.segments
            if len(points) < 2:
                continue

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

    def _get_relevant_segments(self, origin: Tuple[float, float], radius: float) -> List[int]:
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
        self, origin: Tuple[float, float], vision_range: float, token_id: Optional[int] = None
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
            
            polygon.append((
                origin[0] + min_t * dx,
                origin[1] + min_t * dy
            ))

        # 4. Update cache before returning
        if token_id is not None:
            self.cache[cache_key] = polygon
            
        return polygon
