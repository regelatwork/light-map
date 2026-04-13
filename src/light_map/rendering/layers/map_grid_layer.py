import cv2
import numpy as np
import math
from typing import List
from light_map.core.common_types import Layer, LayerMode, ImagePatch, GridType
from light_map.state.world_state import WorldState
from light_map.core.geometry import PointyTopHex, FlatTopHex


class MapGridLayer(Layer):
    """
    Renders a grid of crosses based on the calibration state.
    This replaces the manual drawing in MapGridCalibrationScene.render.
    """

    def __init__(self, state: WorldState, width: int, height: int):
        # Requirements: state, width, height. is_static=False, layer_mode=LayerMode.NORMAL.
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        # Requirements: return max(self.state.grid_metadata_version, self.state.viewport_version).
        if self.state is None:
            return 0
        return max(self.state.grid_metadata_version, self.state.viewport_version)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        """
        Logic ported from MapGridCalibrationScene.render.
        Updated to account for viewport rotation.
        """
        if not self.state:
            return []

        grid = self.state.grid_metadata
        vp = self.state.viewport

        if grid.spacing_svg <= 0:
            return []

        # spacing = spacing_svg * zoom
        spacing = grid.spacing_svg * vp.zoom
        if spacing <= 1.0:  # Prevent infinite loop or too many crosses
            return []

        # Transform origin (Accounting for map rotation)
        # MapSystem uses center-of-screen as rotation pivot:
        cx, cy = self.width / 2, self.height / 2

        # 1. Scale relative to world origin (0,0)
        wx_scaled = grid.origin_svg_x * vp.zoom
        wy_scaled = grid.origin_svg_y * vp.zoom

        # 2. Rotate around screen center (cx, cy)
        angle_rad = math.radians(vp.rotation)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        dx = wx_scaled - cx
        dy = wy_scaled - cy

        rx = dx * cos_a - dy * sin_a
        ry = dx * sin_a + dy * cos_a

        # 3. Translate by viewport offset
        off_x = rx + cx + vp.x
        off_y = ry + cy + vp.y

        # Create transparent BGRA buffer
        buffer = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        color_green = (0, 255, 0, 255)  # BGRA
        color_black = (0, 0, 0, 255)
        cross_size = 10  # Length of each arm in pixels

        # Calculate range of intersection indices covering the screen
        # We find the screen corners in grid-relative space
        inv_cos = math.cos(-angle_rad)
        inv_sin = math.sin(-angle_rad)

        corners = [(0, 0), (self.width, 0), (0, self.height), (self.width, self.height)]
        min_i, max_i = float("inf"), float("-inf")
        min_j, max_j = float("inf"), float("-inf")

        for cx_s, cy_s in corners:
            # Shift back by viewport translation and pivot
            cdx = cx_s - vp.x - cx
            cdy = cy_s - vp.y - cy
            # Rotate back
            crx = cdx * inv_cos - cdy * inv_sin
            cry = cdx * inv_sin + cdy * inv_cos
            # Shift back to scaled world
            wx_c = crx + cx
            wy_c = cry + cy

            # Distance from grid origin in grid units
            i = (wx_c - wx_scaled) / spacing
            j = (wy_c - wy_scaled) / spacing

            min_i, max_i = min(min_i, i), max(max_i, i)
            min_j, max_j = min(min_j, j), max(max_j, j)

        start_i = int(math.floor(min_i))
        end_i = int(math.ceil(max_i))
        start_j = int(math.floor(min_j))
        end_j = int(math.ceil(max_j))

        # Security limit to avoid hang if spacing is very small but > 1.0
        if (end_i - start_i + 1) * (end_j - start_j + 1) > 10000:
            return []

        if grid.type == GridType.SQUARE:
            for i in range(start_i, end_i + 1):
                rel_x = i * spacing
                for j in range(start_j, end_j + 1):
                    rel_y = j * spacing

                    # Rotate relative vector
                    rot_rel_x = rel_x * cos_a - rel_y * sin_a
                    rot_rel_y = rel_x * sin_a + rel_y * cos_a

                    # Final screen position
                    x = int(round(off_x + rot_rel_x))
                    y = int(round(off_y + rot_rel_y))

                    if not (0 <= x < self.width and 0 <= y < self.height):
                        continue

                    # Draw cross with outline
                    cv2.line(
                        buffer, (x - cross_size, y), (x + cross_size, y), color_black, 3
                    )
                    cv2.line(
                        buffer, (x - cross_size, y), (x + cross_size, y), color_green, 1
                    )

                    cv2.line(
                        buffer, (x, y - cross_size), (x, y + cross_size), color_black, 3
                    )
                    cv2.line(
                        buffer, (x, y - cross_size), (x, y + cross_size), color_green, 1
                    )
        else:
            # Hex Grid
            hex_geo = PointyTopHex(spacing) if grid.type == GridType.HEX_POINTY else FlatTopHex(spacing)
            
            # Offset center for vertices
            v_offsets = []
            for i in range(6):
                angle_deg = 60 * i + (30 if grid.type == GridType.HEX_POINTY else 0)
                angle_rad = math.radians(angle_deg)
                v_offsets.append((hex_geo.size * math.cos(angle_rad), hex_geo.size * math.sin(angle_rad)))

            for i in range(start_i, end_i + 1):
                for j in range(start_j, end_j + 1):
                    # Bounding box coordinates from start_i/end_i are for square grid,
                    # but they cover the screen area sufficiently for axial coords too.
                    rel_x, rel_y = hex_geo.to_pixel(i, j)

                    # Rotate center
                    rot_rel_x = rel_x * cos_a - rel_y * sin_a
                    rot_rel_y = rel_x * sin_a + rel_y * cos_a
                    cx_s = off_x + rot_rel_x
                    cy_s = off_y + rot_rel_y

                    # Skip if too far from screen
                    if not (-spacing <= cx_s < self.width + spacing and -spacing <= cy_s < self.height + spacing):
                        continue

                    # Draw Hexagon
                    pts = []
                    for vx, vy in v_offsets:
                        # Rotate vertex offset
                        rvx = vx * cos_a - vy * sin_a
                        rvy = vx * sin_a + vy * cos_a
                        pts.append([int(round(cx_s + rvx)), int(round(cy_s + rvy))])
                    
                    cv2.polylines(buffer, [np.array(pts)], True, color_black, 3)
                    cv2.polylines(buffer, [np.array(pts)], True, color_green, 1)

        # Highlight Origin specifically
        ox, oy = int(round(off_x)), int(round(off_y))
        if 0 <= ox < self.width and 0 <= oy < self.height:
            cv2.circle(buffer, (ox, oy), 8, color_black, -1)
            cv2.circle(buffer, (ox, oy), 5, (0, 255, 0, 255), -1)

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=buffer,
            )
        ]
