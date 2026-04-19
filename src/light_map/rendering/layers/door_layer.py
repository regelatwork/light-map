import cv2
import numpy as np
import math
import svgelements
from typing import List
from light_map.core.common_types import Layer, ImagePatch, LayerMode
from light_map.state.world_state import WorldState
from light_map.visibility.visibility_types import VisibilityType


class DoorLayer(Layer):
    """
    Renders door highlights on the map.
    Only renders doors that have been discovered by tokens.
    """

    def __init__(
        self,
        state: WorldState,
        width: int,
        height: int,
        thickness_multiplier: float = 3.0,
    ):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.NORMAL)
        self.width = width
        self.height = height
        self.thickness_multiplier = thickness_multiplier

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(
            self.state.visibility_version,
            self.state.viewport_version,
            self.state.grid_metadata_version,
            self.state.fow_version, # To pick up door discovery
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        image = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        if not self.state or not self.state.viewport:
            return []

        vp = self.state.viewport
        grid = self.state.grid_metadata
        cx, cy = self.width / 2, self.height / 2

        # Transformation Matrix: SVG -> Screen
        m_svg_to_screen = svgelements.Matrix()
        m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
        m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
        m_svg_to_screen.post_translate(vp.x, vp.y)

        # Dynamic Thickness
        spacing = grid.spacing_svg
        base_wall_thickness = (spacing / 16.0) * vp.zoom
        yellow_thickness = max(2, int(base_wall_thickness * self.thickness_multiplier))
        padding = max(2, int(2.0 * (spacing / 16.0) * vp.zoom))
        black_thickness = yellow_thickness + padding
        circle_radius = max(3, int(yellow_thickness * 0.8))
        circle_outline = circle_radius + max(2, int(padding / 2))

        # Colors (BGRA)
        YELLOW = (0, 255, 255, 255)
        BLACK = (0, 0, 0, 255)

        discovered_ids = self.state.discovered_ids

        for blocker in self.state.blockers:
            if blocker.type != VisibilityType.DOOR:
                continue
            
            # Object-Based Discovery Check
            if blocker.id not in discovered_ids:
                continue

            # Transform points
            transformed_points = []
            for sx, sy in blocker.points:
                p = m_svg_to_screen.point_in_matrix_space((sx, sy))
                transformed_points.append((int(p.x), int(p.y)))

            if len(transformed_points) < 2:
                continue

            if blocker.is_open:
                # Render endpoints as circles
                for pt in transformed_points:
                    cv2.circle(image, pt, circle_outline, BLACK, -1, lineType=cv2.LINE_AA)
                    cv2.circle(image, pt, circle_radius, YELLOW, -1, lineType=cv2.LINE_AA)
            else:
                # Render as thick yellow line
                pts_array = np.array(transformed_points, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(image, [pts_array], False, BLACK, thickness=black_thickness, lineType=cv2.LINE_AA)
                cv2.polylines(image, [pts_array], False, YELLOW, thickness=yellow_thickness, lineType=cv2.LINE_AA)

        return [ImagePatch(x=0, y=0, width=self.width, height=self.height, data=image)]
